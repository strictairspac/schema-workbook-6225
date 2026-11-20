import {esc,date} from '../utils/html.js';
import {session} from '../hooks/session.js';
import {SYNC_STATES} from '../constants/enums.js';
export const syncBadge=s=>`<span class="badge ${esc(s)}">${esc(SYNC_STATES[s]||s)}</span>`;
function subrelationBlock(attrs,i,rows,writer){
  const mine=rows.filter(x=>x.subrelation===i);
  return `<section class="subrelation"><div class="section-top"><h3>R${i+1} · ${attrs.map(a=>`<span class="attribute">${esc(a)}</span>`).join(' ')}</h3><span>${mine.length} 行</span></div>
  ${mine.length?`<div class="table-wrap"><table><thead><tr>${attrs.map(a=>`<th>${esc(a)}</th>`).join('')}<th>状态</th><th>操作</th></tr></thead><tbody>${mine.map(x=>`<tr>${attrs.map(a=>`<td>${esc(x.values[a]??'')}</td>`).join('')}<td>${syncBadge(x.sync)}</td><td><button class="link edit-sample" data-id="${x.id}" data-sub="${i}" ${writer?'':'disabled'}>更正</button><button class="link del-sample" data-id="${x.id}" ${writer?'':'disabled'}>撤掉</button></td></tr>`).join('')}</tbody></table></div>`:'<p class="help">这个分表还没有样本行，录入后即可参与拼接。</p>'}
  <form class="sample-form" data-sub="${i}"><input type="hidden" name="sample_id">${attrs.map(a=>`<label>${esc(a)}<input name="attr:${esc(a)}" maxlength="120" required ${writer?'':'disabled'}></label>`).join('')}<button class="primary" ${writer?'':'disabled'}>录入样本行 +</button><button type="button" class="link cancel-edit" hidden>取消更正</button></form></section>`;
}
export function assemblySection(report,samples,assembly){
  if(!report||report.status!=='completed'||!report.result)return '';
  const writer=session.user?.role!=='viewer';
  const subs=samples?.subrelations||[],rows=samples?.rows||[];
  const a=assembly||{version:0,rows:[],pending:0,refreshing:false,attributes:report.result.attributes};
  const stale=a.pending>0||a.refreshing;
  const head=a.version?`v${a.version} · ${date(a.published_at)}`:'尚未发布拼接版本';
  const attrs=a.attributes||[];
  return `<div class="section-top"><h2>分表样本行</h2><span>NATURAL JOIN / 同名属性拼接</span></div>
  <p class="help">值班员在各分表录入样本行，后台按同名属性自然连接拼回完整委托。更正只重算受影响的组合，关联值改动前后都会重算；同一委托若还有别的拼接来源，撤掉一条也会保留。</p>
  <div class="subrelations">${subs.map((attrs,i)=>subrelationBlock(attrs,i,rows,writer)).join('')}</div>
  <div class="section-top"><h2>拼回委托 ${syncBadge(stale?'pending':'synced')}</h2><span>${esc(head)}</span></div>
  ${stale?`<div class="notice">${a.refreshing?'刷新进行中':'有 '+a.pending+' 条更正待应用'} · 整批拼好并发布前，页面继续显示上一版${a.version?'（v'+a.version+'）':''}。</div>`:''}
  ${a.rows.length?`<div class="table-wrap"><table><thead><tr>${attrs.map(x=>`<th>${esc(x)}</th>`).join('')}<th>拼接来源数</th></tr></thead><tbody>${a.rows.map(r=>`<tr>${attrs.map(x=>`<td>${esc(r.values[x]??'')}</td>`).join('')}<td>${r.sources}</td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">还没有拼好的委托。先在上方各分表录入样本行。</div>'}
  ${writer?'<p><button id="assembly-refresh" class="link">立即刷新拼接 ↗</button></p>':''}`;
}
