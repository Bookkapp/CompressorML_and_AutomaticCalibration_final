import React from "react";
import {
  BookOpen, CheckCircle2, ShieldCheck, AlertTriangle, Cpu, Database,
  SlidersHorizontal, Clock3, Lock, Zap, ArrowRight, HelpCircle
} from "lucide-react";

export function EngineeringManual() {
  return (
    <div className="manual-container">
      {/* Hero Header */}
      <section className="manual-hero">
        <div className="manual-hero-content">
          <div className="hero-icon-box">
            <BookOpen size={28} color="#139c82" />
          </div>
          <div>
            <h2>OPERATION P — Engineering Manual & Standard Operating Procedure</h2>
            <p>
              คู่มือขั้นตอนการปรับเทียบ (Calibration SOP), กฎเกณฑ์การคัดกรองข้อมูล (State Gates) และพจนานุกรมรหัสเหตุผล (Reason Codes Codebook) สำหรับวิศวกรและช่างผู้รับผิดชอบระบบ
            </p>
          </div>
        </div>
      </section>

      {/* Section 1: Standard Operating Procedure (SOP) */}
      <section className="manual-card">
        <div className="manual-card-header">
          <SlidersHorizontal size={20} className="header-icon" />
          <div>
            <h3>1. Standard Operating Procedure (ขั้นตอนการทำงานมาตรฐาน 4 ขั้นตอน)</h3>
            <p>โฟลว์การปรับเทียบและเปิดใช้งานโมเดลวิเคราะห์ความผิดปกติแบบ Zero-PLC-Write และ Human-Approval Gate</p>
          </div>
        </div>

        <div className="sop-grid">
          <div className="sop-step">
            <div className="sop-step-badge">ขั้นตอนที่ 1</div>
            <h4>Machine Discovery</h4>
            <p>
              ระบบเฝ้าฟัง Telemetry Stream จากตาราง <code>tb_data_logger_n</code> และลงทะเบียนเครื่องจักรอัตโนมัติ ตรวจสอบจำนวนแถวข้อมูลและช่วงเวลาล่าสุด
            </p>
            <div className="sop-step-tag">Source Detection</div>
          </div>

          <div className="sop-step">
            <div className="sop-step-badge">ขั้นตอนที่ 2</div>
            <h4>State Qualification Gate</h4>
            <p>
              คัดกรองเฉพาะข้อมูลช่วง <strong>Cold Run Steady State</strong> (Compressor ON, Cold State, SV Valve OFF, Busy 0) และตัดช่วง Transient, Pump-down ออกเพื่อป้องกันข้อมูลปนเปื้อน
            </p>
            <div className="sop-step-tag">Data Sanitization</div>
          </div>

          <div className="sop-step">
            <div className="sop-step-badge">ขั้นตอนที่ 3</div>
            <h4>Baseline & Shadow Validation</h4>
            <p>
              คำนวณ Robust Medians, Scales (P10–P90) และทดสอบย้อนหลังในหน้าต่าง <strong>3-Day Forward Shadow Window</strong> เพื่อประเมินอัตรา False Positive ก่อนส่งให้ตรวจสอบ
            </p>
            <div className="sop-step-tag">Statistical Validation</div>
          </div>

          <div className="sop-step">
            <div className="sop-step-badge">ขั้นตอนที่ 4</div>
            <h4>Review & Active Frozen</h4>
            <p>
              วิศวกรหรือช่างผู้มีอำนาจ (Authorized Approver) ตรวจสอบค่าพารามิเตอร์และกด <strong>Approve</strong> เพื่อเปิดใช้เป็น Active Profile พร้อมบันทึก Rollback Pointer
            </p>
            <div className="sop-step-tag active-tag">Production Activation</div>
          </div>
        </div>
      </section>

      {/* Section 2: Operating State Qualification Gate */}
      <section className="manual-card">
        <div className="manual-card-header">
          <Cpu size={20} className="header-icon" />
          <div>
            <h3>2. Qualified Operating State Criteria (เกณฑ์การคัดเลือกสภาวะปกติ)</h3>
            <p>ข้อกำหนดสภาวะการทำงานของเครื่องจักร HT-9046MX ที่อนุญาตให้นำมาใช้เป็น Baseline ของโมเดล</p>
          </div>
        </div>

        <div className="rules-grid">
          <div className="rule-box qualified">
            <div className="rule-title">
              <CheckCircle2 size={18} color="#059669" />
              <strong>Qualified States (อนุญาตให้ Calibrate)</strong>
            </div>
            <ul>
              <li><strong>Cold Run Mode:</strong> ระบบทำความเย็นอุณหภูมิต่ำสุดทำงานต่อเนื่องเข้าสู่จุดเสถียร</li>
              <li><strong>Solenoid Valve (SV) = OFF:</strong> วาล์วเร่งหรือบายพาสปิดสนิท แรงดันน้ำยาเข้าสู่วงรอบเสถียร</li>
              <li><strong>Busy State = 0:</strong> ไม่มีคำสั่งขัดจังหวะการทดสอบหรือการหมุนรอบฉุกเฉิน</li>
              <li><strong>Compressor Status = ON:</strong> คอมเพรสเซอร์สเตจ 1 (R507A) และสเตจ 2 (R23) ทำงานปกติ</li>
            </ul>
          </div>

          <div className="rule-box disqualified">
            <div className="rule-title">
              <AlertTriangle size={18} color="#dc2626" />
              <strong>Quarantined States (กักกัน/ห้ามใช้เป็น Baseline)</strong>
            </div>
            <ul>
              <li><strong>Start/Stop Transients:</strong> ช่วง 15 นาทีแรกของการเริ่มเดินเครื่องหรือหยุดเดินเครื่อง</li>
              <li><strong>Emergency Down / Alarm:</strong> สภาวะที่ PLC ตัดการทำงานด้วย Error ALM</li>
              <li><strong>MValveHome / Pump Down:</strong> วาล์วหรือระบบกำลังระบายหรือรวบรวมสารทำความเย็น</li>
              <li><strong>Mixed / Transition Window:</strong> สภาวะที่อุณหภูมิหรือรอบการทำงานแกว่งตัวกะทันหัน</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Section 3: Reason Codes Codebook */}
      <section className="manual-card">
        <div className="manual-card-header">
          <HelpCircle size={20} className="header-icon" />
          <div>
            <h3>3. Reason Codes Codebook (พจนานุกรมรหัสเหตุผลและการแก้ปัญหา)</h3>
            <p>ความหมายของ Codebook ที่แสดงบนโปรไฟล์ และแนวทางปฏิบัติเมื่อระบบติด Gate</p>
          </div>
        </div>

        <div className="codebook-table-wrapper">
          <table className="codebook-table">
            <thead>
              <tr>
                <th style={{ width: "220px" }}>Reason Code</th>
                <th style={{ width: "130px" }}>สถานะ Gate</th>
                <th>ความหมายทางวิศวกรรม</th>
                <th>แนวทางปฏิบัติ / วิธีการปลดล็อค</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><code>INSUFFICIENT_CALIBRATION_COVERAGE</code></td>
                <td><span className="pill pill-amber">Gate ติดค้าง</span></td>
                <td>
                  เครื่องจักรมีจำนวน Qualified Windows น้อยกว่า 5 รอบการประเมิน (ไม่เพียงพอต่อการประมาณค่าสถิติ Robust Scale ได้อย่างแม่นยำ)
                </td>
                <td>
                  เดินเครื่องในโหมด Cold Run อย่างน้อย 1–2 กะการทำงาน หรือกดรัน Active Calibration ใหม่โดยระบบจะดึง <strong>Fleet Prior Bootstrapped</strong> ให้อัตโนมัติ
                </td>
              </tr>
              <tr>
                <td><code>BOOTSTRAPPED_FROM_FLEET_PRIOR</code></td>
                <td><span className="pill pill-blue">ปรับเทียบแบบยืมอิง</span></td>
                <td>
                  เครื่องจักรมีข้อมูลเดินเครื่องน้อย (5–49 windows) ระบบจึงใช้ <strong>Stein Shrinkage Empirical Bayes</strong> เฉลี่ยถ่วงน้ำหนักร่วมกับ Fleet Baseline ที่ผ่านการตรวจรับรองแล้ว (MX080) เพื่อให้พร้อมทำงานได้ทันที
                </td>
                <td>
                  สามารถอนุมัติ (Approve) ใช้งานเป็น Active Profile ได้ทันที และเมื่อเครื่องจักรสะสมชั่วโมง Cold Run ครบ 50 windows ระบบจะปรับเป็น Local Baseline อัตโนมัติ
                </td>
              </tr>
              <tr>
                <td><code>SHADOW_FLAG_RATE_EXCEEDED</code></td>
                <td><span className="pill pill-red">ต้องตรวจสอบ</span></td>
                <td>
                  ในช่วง 3-Day Forward Shadow Validation พบอัตราการแจ้งเตือนสูงเกินเกณฑ์ความปลอดภัย (&gt; 5%) แสดงว่าพารามิเตอร์ Baseline แคบเกินไป หรือเครื่องจักรมีความผันผวน
                </td>
                <td>
                  ตรวจสอบกราฟ Shadow ในหน้ารายละเอียด หากพบว่าเป็นสภาวะผิดปกติจริงของเครื่อง ให้บำรุงรักษาเครื่องก่อน หรือหากเป็นจุดวัดแกว่งชั่วคราว ให้ขยาย Lookback เป็น 60 วันแล้วคำนวณใหม่
                </td>
              </tr>
              <tr>
                <td><code>CALIBRATION_DRIFT_EXCEEDED</code></td>
                <td><span className="pill pill-amber">เตือนความเบี่ยงเบน</span></td>
                <td>
                  การทดสอบ Half-shift Drift Test ตรวจพบว่าค่าเฉลี่ยหรือ Median ในครึ่งแรกกับครึ่งหลังของช่วงเวลา Calibration มีความต่างกันเกิน 2.5 Robust Z-Score
                </td>
                <td>
                  ตรวจสอบว่ามีการเปลี่ยนชิ้นส่วน เติมน้ำยา หรือเปลี่ยนสภาวะโหลดหรือไม่ หากเป็นการปรับปรุงเครื่องจักร ให้กด Force Recalculate หลังการบำรุงรักษา
                </td>
              </tr>
              <tr>
                <td><code>STATE_CONTRACT_VERSION_UNVERIFIED</code></td>
                <td><span className="pill pill-grey">รอคำนิยาม</span></td>
                <td>
                  โครงสร้างข้อมูลในตาราง Telemetry มีชื่อฟิลด์หรือรหัสสถานะไม่ตรงกับ Codebook ปัจจุบันของ PLC
                </td>
                <td>
                  ติดต่อ Data/Platform Engineer เพื่ออัปเดต Mapping ให้สอดคล้องกับ PLC Firmware Release ล่าสุด
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Section 4: Production Safety Rules & Guardrails */}
      <section className="manual-card">
        <div className="manual-card-header">
          <ShieldCheck size={20} className="header-icon" />
          <div>
            <h3>4. Safety Guardrails & Governance (กติกาความปลอดภัยทางวิศวกรรม)</h3>
            <p>ข้อบังคับความปลอดภัยที่ระบบ OPERATION P ปฏิบัติตามอย่างเคร่งครัดตามกติกา AGENTS.md</p>
          </div>
        </div>

        <div className="guardrails-grid">
          <div className="guardrail-item">
            <Lock size={20} color="#139c82" />
            <div>
              <strong>Strict Read-Only Boundary (Zero PLC Write)</strong>
              <span>
                ระบบทำงานในโหมด Shadow Screening แบบอ่านข้อมูลจาก MySQL เท่านั้น ไม่มีช่องทางส่งสัญญาณเขียนกลับไปยัง PLC หรือกลไกควบคุมเครื่องจักร
              </span>
            </div>
          </div>

          <div className="guardrail-item">
            <Zap size={20} color="#139c82" />
            <div>
              <strong>Hp_2nd Qualified Reference Band (180–230 psi)</strong>
              <span>
                ช่วง 180–230 psi เป็นช่วงอ้างอิงหน้างานเมื่อเครื่องอยู่ใน Qualified State หากต่ำกว่า 180 psi ใช้เป็นหลักฐานคัดกรองเบื้องต้น (Screening) ห้ามสรุปว่ารั่วโดยไม่มีการตรวจจริง
              </span>
            </div>
          </div>

          <div className="guardrail-item">
            <ShieldCheck size={20} color="#139c82" />
            <div>
              <strong>Immutable Active Frozen Profiles</strong>
              <span>
                โปรไฟล์ที่ถูกอนุมัติเข้าสู่ Production จะล็อกสถานะเป็น <code>ACTIVE_FROZEN</code> ระบบอัตโนมัติไม่มีสิทธิ์เขียนทับ ต้องผ่านการอนุมัติจากวิศวกรทุกครั้ง
              </span>
            </div>
          </div>

          <div className="guardrail-item">
            <Clock3 size={20} color="#139c82" />
            <div>
              <strong>Transactional Rollback & Fail-Closed</strong>
              <span>
                ทุกครั้งที่มีการอนุมัติโปรไฟล์ใหม่ ระบบจะบันทึก <code>rollback_profile_id</code> เดิมไว้เสมอ หากมีปัญหา สามารถย้อนกลับได้ทันทีโดยไม่หยุดชะงัก
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
