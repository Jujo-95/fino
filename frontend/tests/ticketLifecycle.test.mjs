import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const source=readFileSync(new URL('../src/ticketLifecycle.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
const context={exports:{},Date};
runInNewContext(compiled,context);
const {taskState,taskStateLabel,isDeferred,isActiveTask,taskCounts}=context.exports;

test('existing ticket histories retain their meaning without exposing technical states',()=>{
  for(const [status,kind,label] of [
    ['PROPOSED','finding','Por hacer'],['APPROVED','finding','Por hacer'],
    ['REJECTED','finding','Por hacer'],['IMPLEMENTED','finding','En seguimiento'],
    ['IMPLEMENTED','onboarding','Resuelto'],['MONITORING','finding','En seguimiento'],
    ['RESOLVED','finding','Resuelto'],['FALSE_POSITIVE','finding','Descartado']
  ])assert.equal(taskStateLabel({status,ticket_kind:kind}),label);
});

test('registered actions stay active while verified work is complete',()=>{
  assert.equal(isActiveTask({status:'IMPLEMENTED',ticket_kind:'finding'}),true);
  assert.equal(isActiveTask({status:'IMPLEMENTED',ticket_kind:'onboarding'}),false);
  assert.equal(taskState({status:'REJECTED'}),'todo');
  const tickets=['PROPOSED','APPROVED','IMPLEMENTED','MONITORING','RESOLVED','FALSE_POSITIVE'].map(status=>({status}));
  assert.deepEqual(JSON.parse(JSON.stringify(taskCounts(tickets))),{todo:2,monitoring:2,resolved:1,dismissed:1});
});

test('future reminders are hidden until due and old undated reminders stay recoverable',()=>{
  assert.equal(isDeferred({status:'SNOOZED',snoozed_until:'2027-01-02'},'2027-01-01'),true);
  assert.equal(isDeferred({status:'SNOOZED',snoozed_until:'2027-01-01'},'2027-01-01'),false);
  assert.equal(isDeferred({status:'SNOOZED'},'2027-01-01'),true);
});
