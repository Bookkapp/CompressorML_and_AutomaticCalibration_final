import {useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {api} from "../api";
import type {FleetTransitions,ContextTemplate} from "../context-types";
import {ContextChart} from "./ContextChart";

export function FleetTransitionReview({data,accepted,onChange,origins,includedSV,disabled,onRefresh,error}:{data?:FleetTransitions;accepted:string[];onChange:(v:string[])=>void;origins:string[];includedSV:string[];disabled:boolean;onRefresh:()=>void;error?:unknown}){
  const [example,setExample]=useState<NonNullable<ContextTemplate['fleet_assistance']>['examples'][number]|null>(null);
  const chart=useQuery({queryKey:['fleet-transition-example',data?.bundle_id,example?.machine,example?.module,example?.at],queryFn:()=>api.fleetStableDay(`MX${example!.machine}`,example!.module,example!.at.slice(0,10),data!.bundle_id),enabled:!!example&&!!data,staleTime:300000,retry:false});
  const rows=(chart.data?.chart??[]).filter(p=>example&&Math.abs(Date.parse(p.time)-Date.parse(example.at))<=45*60000).map(p=>({time:p.time,...p.features}));
  return <section className="context-review-card"><header><h3>Reference ของ Transition จาก Fleet</h3><button type="button" onClick={onRefresh}>อัปเดต Fleet Transition</button></header>
    {!!error&&<p role="alert" className="form-error">{String(error)}</p>}
    <p className="context-help">ยืมรูปแบบการตอบสนองจากเครื่องอื่นที่ผ่านการเทียบสภาวะเริ่มต้น ระดับแรงดันอ้างอิงของเครื่องนี้ยังคงเดิม · ต้องรับรองสภาวะก่อนเหตุการณ์ และตรวจว่า hardware / configuration ตรงกันก่อนเลือกใช้</p>
    {!data?.templates.length&&<p className="context-help">ยังไม่มี Fleet Transition ที่เข้ากันได้และมีตัวอย่างพอสำหรับโมดูลนี้ {data?.status==='CATALOG_NOT_PREPARED'?'· เลือกรุ่น Fleet ที่มี Transition ในหน้า Fleet Models':''}</p>}
    {data?.templates.map(t=>{const origin=t.key.split('|')[1].replace('FROM_','');const eligible=origins.includes(origin)&&includedSV.some(sv=>t.key.endsWith(`_SV_${sv}`));return <article className="context-regime" key={t.template_id}>
      <label className="context-check"><input type="checkbox" disabled={disabled||!eligible} checked={accepted.includes(t.template_id)} onChange={e=>onChange(e.target.checked?[...accepted,t.template_id]:accepted.filter(id=>id!==t.template_id))}/><strong>{t.key.split('|')[0].replaceAll('_',' ')} · Fleet assisted</strong></label>
      <p className="context-help">จาก {t.fleet_assistance?.donor_machines.map(m=>`MX${m}`).join(', ')} · {t.events} รอบ · {t.days} วัน · Local {t.fleet_assistance?.local_events} รอบ</p>
      {!eligible&&<p className="context-help">เลือกสภาวะก่อนเหตุการณ์และ SV ที่รองรับก่อน</p>}
      <details><summary>ตรวจตัวอย่างข้อมูลจริงจากเครื่องต้นทาง</summary><div className="context-example-buttons">{t.fleet_assistance?.examples.slice(0,24).map(e=><button type="button" key={e.event_id} onClick={()=>setExample(e)}>MX{e.machine} / M{e.module} · {e.at.replace('T',' ')}</button>)}</div></details>
    </article>})}
    {example&&<section><header><h4>MX{example.machine} / M{example.module} · {example.at.replace('T',' ')}</h4><button type="button" onClick={()=>setExample(null)}>ปิดตัวอย่าง</button></header><p className="context-help">ค่าที่วัดจริงเฉลี่ยรายนาที ±45 นาที · psi · Asia/Bangkok · ช่วงนี้ยังไม่ได้รับรองว่า Normal</p>{chart.error&&<p role="alert" className="form-error">{String(chart.error)}</p>}<div className="context-chart-card" aria-busy={chart.isFetching}><ContextChart rows={rows} kind="pressure" highlight={[example.at,example.at]}/></div></section>}
    {!!data?.rejected.length&&<details><summary>เหตุผลที่ Fleet ยังช่วยไม่ได้ · {data.rejected.length} รูปแบบ</summary><ul>{data.rejected.map((r,i)=><li key={i}>{r.key.split('|')[0].replaceAll('_',' ')} · {r.reason==='OBSERVED_ORIGIN_REFERENCE_REQUIRED'?'ยังไม่มี Reference ของสภาวะก่อนเหตุการณ์':'เครื่องต้นทางที่เข้ากันได้และผ่านการทดสอบอิสระยังไม่พอ'}{r.transfer_receipts?.map((d,j)=><p className="context-help" key={j}>MX{d.machine} · {d.holdout?`ทดสอบ ${d.holdout.events} รอบ · ออกนอกกรอบ ${d.holdout.outside_minutes} / ${d.holdout.evaluated_minutes} นาที`:'ยังไม่มีผลทดสอบอิสระ'} · {d.reason==='ELIGIBLE_FOR_REVIEW'?'พร้อมทบทวน':d.reason==='ORIGIN_INCOMPATIBLE'?'สภาวะเริ่มต้นไม่เข้ากัน':'ต้องตรวจ Transition เพิ่ม'}{d.examples?.map(e=><button type="button" key={e.event_id} onClick={()=>setExample(e)}>ดูกราฟ MX{e.machine} · {e.at.replace('T',' ')}</button>)}</p>)}</li>)}</ul></details>}
  </section>;
}
