import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
const source=readFileSync(new URL('../src/hooks/useUrlState.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
function harness(path){
  const url=new URL(path,'https://finops.test');let navigation;
  const location={pathname:url.pathname,search:url.search};const params=new URLSearchParams(url.search);
  const router={useLocation:()=>location,useNavigate:()=>next=>{navigation=next},
    useSearchParams:()=>[params,fn=>{navigation={pathname:url.pathname,search:fn(params).toString()}}]};
  const context={exports:{},URLSearchParams,require:()=>router};runInNewContext(compiled,context);
  return {state:context.exports.useUrlState,navigation:()=>navigation};
}
for(const [page,key,id] of [['tickets','ticket','FIN-011'],['chat','conversation','abc123'],['reports','run','run123']]){
  test(`${page} restores resource identity and retains panel preferences`,()=>{
    const h=harness(`/clients/acme/${page}/${id}?mode=list&thread=FIN-002`);
    const [value,set]=h.state(key);assert.equal(value,id);set('next');
    assert.equal(h.navigation().pathname,`/clients/acme/${page}/next`);
    assert.equal(new URLSearchParams(h.navigation().search).get('thread'),'FIN-002');
  });
}
test('changing objective returns to its ticket list and clears the old thread',()=>{
  const h=harness('/clients/acme/tickets/FIN-011?thread=FIN-011&mode=focus');
  h.state('goal')[1]('allocation');const next=h.navigation();
  assert.equal(next.pathname,'/clients/acme/tickets');
  assert.equal(new URLSearchParams(next.search).get('goal'),'allocation');
  assert.equal(new URLSearchParams(next.search).has('thread'),false);
});
test('filters survive independently and identifiers are encoded',()=>{
  const h=harness('/clients/acme/tickets?phase=Informar');h.state('query')[1]('S3 & coste');
  assert.equal(new URLSearchParams(h.navigation().search).get('phase'),'Informar');
  assert.equal(new URLSearchParams(h.navigation().search).get('query'),'S3 & coste');
  const chat=harness('/clients/acme/chat');chat.state('conversation')[1]('a/b');
  assert.equal(chat.navigation().pathname,'/clients/acme/chat/a%2Fb');
});
