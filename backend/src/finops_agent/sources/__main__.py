import argparse
import os
from ..config import WORKSPACES, validate_client
from .models import S3Source, save_source


def main() -> None:
    parser = argparse.ArgumentParser(description='Configure backend-only S3 source credentials from environment')
    parser.add_argument('--client',required=True)
    parser.add_argument('--endpoint',required=True)
    parser.add_argument('--bucket',required=True)
    parser.add_argument('--prefix',default='focus/')
    parser.add_argument('--region',default='us-east-1')
    parser.add_argument('--access-key-env',default='FINOPS_S3_ACCESS_KEY')
    parser.add_argument('--secret-key-env',default='FINOPS_S3_SECRET_KEY')
    args = parser.parse_args()
    workspace = WORKSPACES/validate_client(args.client)
    if not (workspace/'client_profile.yaml').exists():
        parser.error('Create the client before configuring its source')
    key = dict(AccessKeyId=os.environ[args.access_key_env],SecretAccessKey=os.environ[args.secret_key_env])
    source = S3Source(client_id=args.client,endpoint=args.endpoint,bucket=args.bucket,prefix=args.prefix,region=args.region)
    save_source(workspace,source,key)
    print('Source configured. Credentials remain in backend storage with file mode 0600.')


if __name__=='__main__':
    main()
