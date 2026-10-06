import { Area,CartesianGrid,ComposedChart,Legend,Line,ResponsiveContainer,Tooltip,XAxis,YAxis,ReferenceArea,ReferenceLine } from "recharts";
import {memo} from "react";

export type ChartRow={time:string;[key:string]:unknown};
const time=(v:unknown)=>String(v).slice(11,19);
function ContextChartView({rows,kind,unit="psi",highlight,focus}:{rows:ChartRow[];kind:"pressure"|"temperature"|"valve";unit?:string;highlight?:[string,string]|null;focus?:string}){
  const gaps:number[]=[];
  for(let i=1;i<rows.length;i++){const gap=Date.parse(rows[i].time+"Z")-Date.parse(rows[i-1].time+"Z");if(gap>0)gaps.push(gap);}
  const cadence=gaps.length?Math.min(...gaps):60_000;
  const data:ChartRow[]=[];
  rows.forEach((r,i)=>{const x=Date.parse(r.time+"Z");if(i&&x-Date.parse(rows[i-1].time+"Z")>cadence*1.5)data.push({time:"ช่องว่างข้อมูล",x:x-cadence/2});data.push({...r,x});});
  const lines=kind==="pressure"?[["hp1","Hp 1st","#2c78b8"],["lp1","Lp 1st","#80acd0"],["hp2","Hp 2nd","#0d3d68"],["lp2","Lp 2nd","#269e93"]]:
    kind==="temperature"?[["temphi","Temp High","#d1773a"],["templo","Temp Low","#50a4cf"]]:[["valve","Valve command","#7159b7"]];
  return <div className="context-chart"><ResponsiveContainer width="100%" height={280}><ComposedChart data={data} margin={{top:10,right:18,left:3,bottom:8}}>
    <CartesianGrid stroke="#e4ebf1" vertical={false}/><XAxis dataKey="x" type="number" scale="time" domain={["dataMin","dataMax"]} tickFormatter={v=>time(new Date(Number(v)).toISOString())} minTickGap={60} tick={{fontSize:11}}/>
    <YAxis width={58} tick={{fontSize:11}} domain={["auto","auto"]}/><Tooltip labelFormatter={v=>new Date(Number(v)).toISOString().slice(0,19).replace("T"," ")} contentStyle={{fontSize:12}}/>
    <Legend wrapperStyle={{fontSize:12,paddingTop:8}}/>
    {highlight&&<ReferenceArea x1={Date.parse(highlight[0]+"Z")} x2={Date.parse(highlight[1]+"Z")} fill="#e4a149" fillOpacity={.12}/>}
    {focus&&kind!=="valve"&&<Area dataKey={kind==="pressure"?"pressure_range":"temperature_range"} name={`กรอบที่เสนอ · ${focus}`} stroke="none" fill="#778cb6" fillOpacity={.15} connectNulls={false} isAnimationActive={false}/>}
    {data.filter((r,i,a)=>r.transition_event_id&&(!i||r.transition_event_id!==a[i-1].transition_event_id)).slice(0,30).map(r=><ReferenceLine key={String(r.x)} x={Number(r.x)} stroke="#c28c36" strokeDasharray="3 4"/>)}
    {lines.map(([key,label,color])=><Line key={key} dataKey={key} name={`${label}${kind==="pressure"?` (${unit})`:kind==="temperature"?" (°C)":""}`} stroke={color} type={kind==="valve"?"stepAfter":"linear"} dot={false} connectNulls={false} isAnimationActive={false} strokeWidth={key===focus?2.3:1.4}/>)}
  </ComposedChart></ResponsiveContainer></div>;
}
export const ContextChart=memo(ContextChartView);
