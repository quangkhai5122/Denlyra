"use strict";
const $ = (id) => document.getElementById(id);
const state = {clinicId:null,clinic:null,patients:[],staff:[],chairs:[],plans:[],encounters:[]};
const views = {
 overview:["Tổng quan phòng khám","Bộ mẫu kỹ thuật · Quy trình có dữ liệu giả lập"],
 patients:["Bệnh nhân","Hồ sơ tổng hợp · Không lưu dữ liệu thật"],
 schedule:["Lịch hẹn","Kiểm tra xung đột bác sĩ và ghế"],
 odontogram:["Sơ đồ răng mô phỏng","Lưới mã FDI và sự kiện được lưu có lịch sử"],
 encounters:["Lượt khám & ghi chú","Bản nháp, revision và khóa demo — không phải ký EMR"],
 plans:["Liệu trình","Kế hoạch có phiên bản và phụ thuộc công việc"],
 lab:["Labo","Theo dõi yêu cầu và chuyển trạng thái"],
 finance:["Tài chính","Theo dõi khoản thu giả lập, không phải hóa đơn chính thức"],
 audit:["Nhật ký","Lịch sử sự kiện thử nghiệm"]
};
const money = n => new Intl.NumberFormat("vi-VN").format(n) + "đ";
const textNode=(tag,text,cls)=>{const e=document.createElement(tag);e.textContent=String(text||"");if(cls)e.className=cls;return e;};
const row=(title,detail)=>{const d=textNode("div","","listitem");d.append(textNode("strong",title),textNode("span",detail,"dim"));return d;};
const clear=(node,txt)=>{node.replaceChildren();if(txt)node.append(textNode("p",txt,"explain"));};
const toast=(message)=>{const t=$("toast");t.textContent=message;t.classList.remove("hidden");setTimeout(()=>t.classList.add("hidden"),4400);};
async function api(path,options={}){
 const headers = {"X-Demo-Clinic": state.clinicId || "", "X-Demo-Actor": "demo-web-user",...(options.headers||{})};
 const response=await fetch(path,{...options,headers});
 if(!response.ok){let detail=`HTTP ${response.status}`;try{const p=await response.json();detail=p.detail || detail;}catch{}throw new Error(typeof detail==="string"?detail:JSON.stringify(detail));}
 return response.json();
}
function optionsFor(selector,entries,labelKey){document.querySelectorAll(selector).forEach(select=>{const previous=select.value;select.replaceChildren(new Option("— Chọn —",""));for(const x of entries)select.append(new Option(x[labelKey],x.id));if(entries.find(e=>e.id===previous))select.value=previous;});}
function showView(name){for(const v of Object.keys(views))$("view-"+v).classList.toggle("hidden",v!==name);document.querySelectorAll(".navitem").forEach(el=>el.classList.toggle("selected",el.dataset.view===name));$("view-title").textContent=views[name][0];$("view-subtitle").textContent=views[name][1];}
document.querySelectorAll(".navitem").forEach(x=>x.addEventListener("click",()=>showView(x.dataset.view)));
const jsonPost=(url,data)=>api(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
async function loadContext(){
 const data=await api("/api/v1/demo/context");state.clinicId=data.clinic_id;state.staff=data.staff;state.chairs=data.chairs;
 const select=$("clinic-switch");select.replaceChildren();for(const c of data.clinics)select.append(new Option(c.name,c.id));select.value=state.clinicId;
 optionsFor("[data-doctor-options]",data.staff.filter(x=>x.role==="dentist"),"display_name");
 optionsFor("[data-chair-options]",data.chairs,"name");
}
$("clinic-switch").addEventListener("change",async e=>{state.clinicId=e.target.value;await loadContext();await refresh();});
async function refresh(){
 try{
  const [dash,patients,appointments,encounters,plans,labs,charges,payments]=await Promise.all([
   api("/api/v1/dashboard"),api("/api/v1/patients"),api("/api/v1/appointments"),
   api("/api/v1/encounters"),api("/api/v1/treatment-plans"),api("/api/v1/lab-cases"),
   api("/api/v1/finance/charges"),api("/api/v1/finance/payments")]);
  state.patients=patients;state.plans=plans;state.encounters=encounters;
  $("kpi-patient").textContent=dash.patient_count;$("kpi-appointment").textContent=dash.open_appointments;
  $("kpi-plan").textContent=dash.treatment_plan_count;$("kpi-lab").textContent=dash.lab_case_count;
  optionsFor("[data-patient-options]",patients,"display_name");
  const pp=$("plan-picker");pp.replaceChildren(new Option("— Chọn —",""));for(const p of plans)pp.append(new Option(p.title,p.id));
  optionsFor("[data-encounter-options]",encounters.map(e=>({...e,display_name:`Encounter ${e.id.slice(0,8)}`})),"display_name");
  const ep=$("encounter-picker");ep.replaceChildren(new Option("— Chọn —",""));for(const e of encounters)ep.append(new Option(`Encounter ${e.id.slice(0,8)}`,e.id));
  renderList("patient-list",patients,p=>row(p.display_name,`#${p.id.slice(0,8)} · ${p.birth_year||"Chưa ghi năm sinh"}`),"Chưa có bệnh nhân.");
  renderList("appointment-list",appointments,a=>{const item=row(a.reason_demo,`${new Date(a.start_at).toLocaleString("vi-VN")} · ${a.status}`);if(a.status==="confirmed"){const b=textNode("button","Hủy lịch demo","secondary");b.addEventListener("click",()=>perform(()=>jsonPost(`/api/v1/appointments/${a.id}/cancel`,{})));item.append(b);}return item;},"Chưa có lịch hẹn.");
  renderList("encounter-list",encounters,e=>{const item=row(`Encounter #${e.id.slice(0,8)}`,`Bệnh nhân #${e.patient_id.slice(0,8)} · ${e.status}`);const b=textNode("button","Xem bản ghi nháp","secondary");b.addEventListener("click",()=>showNotes(e.id,item));item.append(b);return item;},"Chưa có lượt khám.");
  renderList("plan-list",plans,p=>{const item=row(p.title,`Phiên bản hiện tại: ${p.current_version} · Bệnh nhân #${p.patient_id.slice(0,8)}`);const b=textNode("button","Xem và thao tác","secondary");b.addEventListener("click",()=>showPlan(p.id,item));item.append(b);return item;},"Chưa có kế hoạch.");
  renderList("lab-list",labs,l=>{const item=row(l.title,`Trạng thái: ${l.status}`);const n={requested:"accepted",accepted:"in_progress",in_progress:"ready",ready:"received",received:"verified",revision_requested:"in_progress"}[l.status];if(n){const b=textNode("button",`Chuyển: ${n}`,"secondary");b.addEventListener("click",()=>perform(()=>jsonPost(`/api/v1/lab-cases/${l.id}/state`,{next_status:n})));item.append(b);}return item;},"Chưa có yêu cầu labo.");
  const f=$("finance-list");clear(f);for(const c of charges)f.append(row("Phải thu · "+money(c.amount_vnd),c.label));for(const p of payments)f.append(row("Đã nhận demo · "+money(p.amount_vnd),`Bệnh nhân #${p.patient_id.slice(0,8)}`));if(!charges.length&&!payments.length)clear(f,"Chưa có dữ liệu tài chính.");
 }catch(e){toast(e.message);}
}
function renderList(id,items,render,emptyText){const target=$(id);clear(target);for(const x of items)target.append(render(x));if(!items.length)clear(target,emptyText);}
async function perform(fn){try{await fn();await refresh();toast("Đã lưu dữ liệu mô phỏng.");}catch(e){toast(e.message);}}
async function showNotes(encounterId,item){try{const data=await api(`/api/v1/encounters/${encounterId}/notes`);const container=textNode("div","");for(const note of data){const x=row(`Note #${note.id.slice(0,8)} · ${note.status}`,`Revision ${note.latest_revision} · ${note.locked_digest ? "Integrity marker có" : "Chưa khóa"}`);const last=note.revisions.at(-1);x.append(textNode("div",last?last.content:"","dim"));if(note.status==="draft"){const b=textNode("button","Khóa demo (KHÔNG ký)","secondary");b.addEventListener("click",()=>perform(()=>jsonPost(`/api/v1/notes/${note.id}/demo-lock`,{})));x.append(b);}container.append(x);}if(!data.length)container.append(textNode("p","Chưa có ghi chú.","dim"));item.append(container);}catch(e){toast(e.message);}}
async function showPlan(planId,item){try{const data=await api(`/api/v1/treatment-plans/${planId}`);const box=textNode("div","");box.append(textNode("p",`Phiên bản ${data.version.number} · ${data.version.status}`,"dim"));for(const t of data.tasks){const r=row(t.title,`${t.phase} · ${t.status}`);if(data.version.status==="demo_reviewed"&&t.status!=="completed"){const b=textNode("button","Hoàn thành việc demo","secondary");b.addEventListener("click",()=>perform(()=>jsonPost(`/api/v1/treatment-tasks/${t.id}/demo-complete`,{})));r.append(b);}box.append(r);}const button=textNode("button",data.version.status==="draft"?"Review demo (KHÔNG duyệt lâm sàng)":"Tạo phiên bản mới","secondary");button.addEventListener("click",()=>perform(()=>jsonPost(`/api/v1/treatment-plans/${planId}/${data.version.status==="draft"?"demo-review":"versions"}`,{})));box.append(button);item.append(box);}catch(e){toast(e.message);}}
function bindForm(id,path,serialize){$(id).addEventListener("submit",e=>{e.preventDefault();const fd=new FormData(e.target);const data=serialize(fd);const url=typeof path==="function"?path(fd):path;perform(()=>jsonPost(url,data));});}
const data=fd=>Object.fromEntries(fd.entries());
bindForm("form-patient","/api/v1/patients",fd=>{const p=data(fd);if(!p.birth_year)delete p.birth_year;else p.birth_year=Number(p.birth_year);return p;});
bindForm("form-appointment","/api/v1/appointments",fd=>{const d=data(fd);d.start_at=new Date(d.start_at).toISOString();d.end_at=new Date(d.end_at).toISOString();return d;});
bindForm("form-encounter","/api/v1/encounters",data);
bindForm("form-note",fd=>`/api/v1/encounters/${fd.get("encounter_id")}/notes`,fd=>({content:fd.get("content")}));
bindForm("form-finding",fd=>`/api/v1/encounters/${fd.get("encounter_id")}/findings`,fd=>({tooth_code:fd.get("tooth_code"),surface:fd.get("surface"),finding_text_demo:fd.get("finding_text_demo")}));
bindForm("form-plan","/api/v1/treatment-plans",data);
bindForm("form-task",fd=>`/api/v1/treatment-plans/${fd.get("plan_id")}/tasks`,fd=>({title:fd.get("title"),phase:fd.get("phase")}));
bindForm("form-lab","/api/v1/lab-cases",data);
bindForm("form-charge","/api/v1/finance/charges",fd=>{const d=data(fd);d.amount_vnd=Number(d.amount_vnd);return d;});
bindForm("form-payment","/api/v1/finance/payments",fd=>{const d=data(fd);d.amount_vnd=Number(d.amount_vnd);return d;});
$("navigation").querySelector('[data-view="audit"]').addEventListener("click",async()=>{try{const events=await api("/api/v1/audit-events");renderList("audit-list",events,e=>row(e.action,`${e.subject_type} · ${e.created_at} · ${e.actor_demo}`),"Chưa có hoạt động.");}catch(e){toast(e.message);}});
(async()=>{try{await loadContext();await refresh();}catch(e){toast(e.message);}})();

function drawFDI(){
 const root=$("teeth-svg");const SVG_NS="http://www.w3.org/2000/svg";
 const svg=document.createElementNS(SVG_NS,"svg");svg.setAttribute("viewBox","0 0 584 150");svg.setAttribute("role","group");svg.setAttribute("aria-label","FDI tooth reference grid, demo only");svg.style.width="100%";
 const groups=[Array.from({length:8},(_,i)=>18-i),Array.from({length:8},(_,i)=>21+i),Array.from({length:8},(_,i)=>48-i),Array.from({length:8},(_,i)=>31+i)];
 groups.forEach((codes,g)=>codes.forEach((tooth,i)=>{
  const x=(g%2)*292+i*35+4, y=Math.floor(g/2)*75+5;
  const node=document.createElementNS(SVG_NS,"g");node.setAttribute("tabindex","0");node.setAttribute("role","button");node.setAttribute("aria-label",`Chọn mã răng FDI ${tooth}`);
  const r=document.createElementNS(SVG_NS,"rect");r.setAttribute("x",String(x));r.setAttribute("y",String(y));r.setAttribute("width","31");r.setAttribute("height","49");r.setAttribute("rx","7");r.setAttribute("fill","#e7f5f1");r.setAttribute("stroke","#78b2a8");
  const t=document.createElementNS(SVG_NS,"text");t.setAttribute("x",String(x+15.5));t.setAttribute("y",String(y+28));t.setAttribute("text-anchor","middle");t.setAttribute("font-size","11");t.setAttribute("font-weight","700");t.setAttribute("fill","#164b47");t.textContent=String(tooth);
  const choose=()=>{$("tooth-code").value=String(tooth);};
  node.addEventListener("click",choose);node.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();choose();}});
  node.append(r,t);svg.append(node);
 }));root.replaceChildren(svg);
}
drawFDI();
$("load-findings").addEventListener("click",async()=>{const id=$("odontogram-patient").value;if(!id)return toast("Hãy chọn bệnh nhân demo");try{const res=await api(`/api/v1/patients/${id}/odontogram`);renderList("finding-list",res.findings,x=>row(`Răng FDI ${x.tooth_code} · ${x.surface}`,`${x.finding_text_demo} · ${x.created_at}`),"Chưa có sự kiện demo.");}catch(e){toast(e.message);}});
