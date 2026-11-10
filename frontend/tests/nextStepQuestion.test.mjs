import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
function load(name){
  const source=readFileSync(new URL('../src/'+name+'.ts',import.meta.url),'utf8');
  const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
  const context={exports:{},Date,Intl,require:path=>load(path.replace('./',''))};
  runInNewContext(compiled,context);
  return context.exports;
}
const {nextStepQuestion}=load('nextStepQuestion');
const {taskNextStep}=load('taskGuidance');
const {orderFocusSteps}=load('focusTaskOrder');
test('the suggested question includes the actual ticket and its next action',()=>{
  const ticket={ticket_id:'FIN-017',title:'Confirmar responsable',status:'PROPOSED',recommended_action:'Comparte la lista de equipos',capability:'allocation'};
  const text=nextStepQuestion(ticket);
  assert.ok(text.includes('FIN-017')&&text.includes('Comparte la lista de equipos'));
  assert.ok(text.includes('evidencia actual'));
  assert.ok(!text.includes('FIN-002'));
});
test('completed rows display the recorded result instead of repeating pending work',()=>{
  const ticket={status:'RESOLVED',resolution_note:'Tecnología confirmó al responsable',recommended_action:'Pedir responsable'};
  assert.equal(taskNextStep(ticket),ticket.resolution_note);
  assert.match(taskNextStep({...ticket,status:'MONITORING'}),/ventana de datos/);
});

test('focus puts the actionable recommendation first and completed work last',()=>{
  const tickets=[{ticket_id:'done',status:'RESOLVED'},{ticket_id:'blocked',status:'PROPOSED'},
    {ticket_id:'pending',status:'PROPOSED'},{ticket_id:'next',status:'PROPOSED'}];
  const steps=tickets.map(t=>({ticket_id:t.ticket_id,state:'todo',excluded:false}));
  const ordered=orderFocusSteps(steps,tickets,'next',t=>t.ticket_id==='blocked');
  assert.deepEqual(Array.from(ordered,s=>s.ticket_id),['next','pending','blocked','done']);
  assert.equal(steps[0].ticket_id,'done');
  assert.notEqual(orderFocusSteps(steps,tickets,'blocked',t=>t.ticket_id==='blocked')[0].ticket_id,'blocked');
});
