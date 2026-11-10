import type {Ticket} from './types';
import {taskNextStep} from './taskGuidance';
import {ticketTitle} from './presentation';
export function nextStepQuestion(ticket:Ticket){
  return `Ayúdame con el siguiente paso de **${ticket.ticket_id}**: ${ticketTitle(ticket)}. ${taskNextStep(ticket)} Revisa sus requisitos y la evidencia actual. Dime de forma concisa qué debo hacer ahora y qué información puedo compartirte si hace falta.`;
}
