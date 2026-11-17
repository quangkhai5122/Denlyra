"use client";
import { useCallback, useEffect, useState, type FormEvent } from "react";

type Clinic = { id: string; name: string };
type Patient = { id: string; display_name: string; birth_year: number | null };
type Staff = { id: string; display_name: string; role: string };
type Chair = { id: string; name: string };
type Context = { clinic_id: string; clinics: Clinic[]; staff: Staff[]; chairs: Chair[] };
type Dashboard = { patient_count: number; open_appointments: number; treatment_plan_count: number };

export default function Home() {
  const [context,setContext] = useState<Context|null>(null);
  const [clinicId,setClinicId] = useState("");
  const [patients,setPatients] = useState<Patient[]>([]);
  const [stats,setStats] = useState<Dashboard|null>(null);
  const [message,setMessage] = useState("");
  const [patientName,setPatientName] = useState("");
  const [planTitle,setPlanTitle] = useState("");
  const [planPatientId,setPlanPatientId] = useState("");

  const api = useCallback(async (path:string, payload?:unknown) => {
    const response=await fetch(`/api/demo/${path}`,{
      method: payload === undefined ? "GET" : "POST",
      headers: {"Content-Type":"application/json", "X-Demo-Clinic":clinicId},
      body: payload === undefined ? undefined : JSON.stringify(payload),
    });
    const body=await response.json();
    if (!response.ok) throw new Error(typeof body.detail === "string"?body.detail:`HTTP ${response.status}`);
    return body;
  },[clinicId]);

  const reload=useCallback(async()=>{
    const [c,p,d]=await Promise.all([api("demo/context"),api("patients"),api("dashboard")]);
    setContext(c as Context);setPatients(p as Patient[]);setStats(d as Dashboard);
    if (!clinicId) setClinicId((c as Context).clinic_id);
  },[api,clinicId]);

  useEffect(()=>{reload().catch(e=>setMessage(String(e.message)));},[reload]);

  async function createPatient(e:FormEvent){e.preventDefault();try{await api("patients",{display_name:patientName});setPatientName("");await reload();setMessage("Đã lưu hồ sơ giả lập.");}catch(err){setMessage(err instanceof Error?err.message:String(err));}}
  async function createPlan(e:FormEvent){e.preventDefault();try{await api("treatment-plans",{patient_id:planPatientId,title:planTitle});setPlanTitle("");await reload();setMessage("Đã tạo kế hoạch nháp giả lập.");}catch(err){setMessage(err instanceof Error?err.message:String(err));}}

  return <main className="shell"><header><div className="brand">✳ Denlyra / React Prototype</div><div className="badge">SYNTHETIC DEMO ONLY</div></header>
    <div className="banner"><strong>KHÔNG PHẢI EMR ĐƯỢC CHỨNG NHẬN.</strong> Giao diện này chỉ minh họa kiến trúc Next.js, sử dụng API demo không có xác thực sản xuất. Không nhập dữ liệu bệnh nhân thật, không ký bệnh án hoặc đưa ra quyết định lâm sàng.</div>
    <label htmlFor="clinic">Phòng khám mô phỏng</label><select id="clinic" value={clinicId} onChange={e=>setClinicId(e.target.value)}>{context?.clinics.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select>
    <div className="cards" style={{marginTop:20}}><div className="card"><span>Bệnh nhân giả lập</span><strong>{stats?.patient_count??"—"}</strong></div><div className="card"><span>Lịch đang hoạt động</span><strong>{stats?.open_appointments??"—"}</strong></div><div className="card"><span>Kế hoạch điều trị</span><strong>{stats?.treatment_plan_count??"—"}</strong></div></div>
    <div className="grid"><section className="card"><h2>Tạo bệnh nhân giả lập</h2><form onSubmit={createPatient}><label htmlFor="patient-name">Tên hiển thị</label><input id="patient-name" minLength={2} value={patientName} onChange={e=>setPatientName(e.target.value)} placeholder="Bệnh nhân Demo ..." required/><button>Tạo hồ sơ demo</button></form></section><section className="card"><h2>Tạo kế hoạch nháp</h2><form onSubmit={createPlan}><label htmlFor="patient-select">Bệnh nhân</label><select id="patient-select" value={planPatientId} onChange={e=>setPlanPatientId(e.target.value)} required><option value="">— Chọn bệnh nhân —</option>{patients.map(p=><option key={p.id} value={p.id}>{p.display_name}</option>)}</select><label htmlFor="plan-title">Tên kế hoạch (giả lập)</label><input id="plan-title" value={planTitle} onChange={e=>setPlanTitle(e.target.value)} required minLength={2}/><button>Tạo kế hoạch</button></form></section></div>
    <div className="grid"><section className="card"><h2>Hồ sơ demo</h2>{patients.length===0?<p className="muted">Chưa có hồ sơ.</p>:patients.map(p=><div className="line" key={p.id}>{p.display_name} <span className="muted">#{p.id.slice(0,8)}</span></div>)}</section><section className="card"><h2>Giới hạn đã biết</h2><p className="muted">Chưa có Next.js screens đầy đủ cho lịch, EMR hay labo. Giao diện demo có đủ các luồng hơn nằm tại backend port 8766. React prototype cần npm install, typecheck và browser QA trước khi dùng cho phát triển chính.</p>{message&&<p role="status" className="muted">{message}</p>}</section></div>
    <footer>Denlyra · Synthetic research demonstrator · Commercial brand clearance pending.</footer></main>;
}
