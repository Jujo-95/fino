export type ProgressStep={ticket_id:string;title:string;state:string;excluded:boolean;reason:string|null;summary:string};
export type ProgressGoal={id:string;title:string;version:number;completed:number;total:number;percent:number|null;complete:boolean;steps:ProgressStep[]};
export type ProgressEvent={id:string;ticket_id:string;title:string;state:string;before:string;at:string;summary:string;evidence?:{criterion?:string|null}};
export type TaskProgress={objective:ProgressGoal|null;objectives:ProgressGoal[];next_action:{ticket_id:string;title:string;reason:string;attention?:string}|null;waiting_for:string|null;history:{resolved_total:number;resolved_this_week:number;observing:number;recent:ProgressEvent[]}};
