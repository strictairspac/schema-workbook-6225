import {api} from './client.js';
export const reportsApi={list:()=>api('/reports'),create:data=>api('/reports','POST',data),
samples:id=>api('/reports/'+id+'/samples'),
addSample:(id,data)=>api('/reports/'+id+'/samples','POST',data),
updateSample:(id,data)=>api('/samples/'+id,'PUT',data),
deleteSample:id=>api('/samples/'+id,'DELETE'),
assembly:id=>api('/reports/'+id+'/assembly'),
refreshAssembly:id=>api('/reports/'+id+'/assembly/refresh','POST')};
