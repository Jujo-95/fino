import json
from pathlib import Path
from typing import Any
import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from ..config import atomic_write_text
from ..sources.models import S3Source, save_source
from .scenarios import SCENARIOS


def aws(service: str, endpoint: str, key: dict[str, str]) -> Any:
    return boto3.client(service,endpoint_url=endpoint,region_name='us-east-1',
        aws_access_key_id=key['AccessKeyId'],aws_secret_access_key=key['SecretAccessKey'],
        config=Config(signature_version='s3v4',request_checksum_calculation='when_required',response_checksum_validation='when_required',s3={'addressing_style':'path'},retries={'max_attempts':1}))


def private_json(path: Path, data: Any) -> None:
    atomic_write_text(path,json.dumps(data,indent=2))
    path.chmod(0o600)


def identity(iam: Any, name: str, resources: list[str], actions: list[str]) -> dict[str, str]:
    iam.create_user(UserName=name)
    key = iam.create_access_key(UserName=name)['AccessKey']
    policy = dict(Version='2012-10-17',Statement=[dict(Effect='Allow',Action=actions,Resource=resources)])
    iam.put_user_policy(UserName=name,PolicyName='lab-scope',PolicyDocument=json.dumps(policy))
    return dict(AccessKeyId=key['AccessKeyId'],SecretAccessKey=key['SecretAccessKey'])


def bootstrap(root: Path, workspaces: Path, endpoint: str) -> None:
    from moto import settings
    settings.INITIAL_NO_AUTH_ACTION_COUNT = float('inf')
    temporary = dict(AccessKeyId='lab-bootstrap',SecretAccessKey='lab-bootstrap')
    iam = aws('iam',endpoint,temporary)
    s3 = aws('s3',endpoint,temporary)
    writer = identity(iam,'lab-publisher',['arn:aws:s3:::finops-lab-*','arn:aws:s3:::finops-lab-*/*'],
                      ['s3:GetObject','s3:PutObject','s3:ListBucket'])
    private_json(root/'publisher.json',dict(endpoint=endpoint,**writer))
    for client_id in SCENARIOS:
        bucket = 'finops-'+client_id
        s3.create_bucket(Bucket=bucket)
        reader = identity(iam,client_id,[f'arn:aws:s3:::{bucket}',f'arn:aws:s3:::{bucket}/focus/*'],
                          ['s3:GetObject','s3:ListBucket'])
        save_source(workspaces/client_id,S3Source(client_id=client_id,endpoint=endpoint,bucket=bucket,prefix="focus/v2/",synthetic=True),reader)
    settings.INITIAL_NO_AUTH_ACTION_COUNT = 0


def publish(root: Path, client_id: str, days: int, restore: bool = False) -> dict[str, Any]:
    if client_id not in SCENARIOS:
        raise ValueError('Unknown laboratory client')
    directory = root/client_id
    manifest = json.loads((directory/'manifest.json').read_text())
    state_path = directory/'published.json'
    old = json.loads(state_path.read_text())['days'] if state_path.exists() else 0
    if not old<=days<=manifest['days']:
        raise ValueError(f'Use a cumulative day count between {old} and {manifest["days"]}')
    credentials = json.loads((root/'publisher.json').read_text())
    s3 = aws('s3',credentials.pop('endpoint'),credentials)
    for part in manifest['partitions'][0 if restore else old:days]:
        s3.put_object(Bucket='finops-'+client_id,Key=part['key'],Body=(directory/part['key']).read_bytes(),
                      ContentType='text/csv',Metadata={'sha256':part['sha256'],'synthetic':'true'})
    result = dict(client_id=client_id,days=days,through=manifest['partitions'][days-1]['day'] if days else None)
    atomic_write_text(state_path,json.dumps(result))
    return result
