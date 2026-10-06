export type ReviewDraft = {
  start: string; end: string; shadowEnd: string; shadowReason: string;
  exclusions: { start: string; end: string; reason: string }[]; note: string;
};

const day = 86_400_000;
const localTime = (value: string) => Date.parse(`${value.length === 10 ? `${value}T00:00` : value}Z`);

// Match the source-local, half-open interval rules before starting a SQL job.
export function draftError(draft: ReviewDraft, latestCutoff?: string): string | null {
  if (Boolean(draft.start) !== Boolean(draft.end)) return "กรอกวันเริ่มและวันสิ้นสุด Reference ให้ครบทั้งสองช่อง";
  if (draft.start && draft.start >= draft.end) return "วันสิ้นสุด Reference ต้องอยู่หลังวันเริ่ม";
  if (draft.shadowEnd && draft.shadowReason.trim().length < 3) return "ระบุเหตุผลเลือกช่วง Shadow ย้อนหลังอย่างน้อย 3 ตัวอักษร";
  const cutoff = draft.shadowEnd || latestCutoff;
  if (!cutoff) return null;
  const shadowEnd = localTime(cutoff);
  if (latestCutoff && (shadowEnd > localTime(latestCutoff) || shadowEnd < localTime(latestCutoff) - 90 * day)) return "Shadow ต้องเป็นวันปิดแล้วและย้อนหลังไม่เกิน 90 วันจากข้อมูลล่าสุด";
  const shadowStart = shadowEnd - 3 * day;
  const start = draft.start ? localTime(draft.start) : shadowStart - 28 * day;
  const end = draft.end ? localTime(draft.end) : shadowStart;
  if (end > shadowStart) return "Reference ต้องสิ้นสุดก่อนเริ่ม Shadow และห้ามใช้ข้อมูลช่วงเดียวกัน";
  if (start < shadowStart - 90 * day) return "Reference ต้องอยู่ภายใน 90 วันก่อนเริ่ม Shadow";
  for (const [i, interval] of draft.exclusions.entries()) {
    if (!interval.start || !interval.end) return `กรอกเวลาเริ่มและจบของช่วงยกเว้น ${i + 1}`;
    if (interval.reason.trim().length < 3) return `ระบุเหตุผลช่วงยกเว้น ${i + 1} อย่างน้อย 3 ตัวอักษร`;
    if (interval.start >= interval.end) return `เวลาจบช่วงยกเว้น ${i + 1} ต้องอยู่หลังเวลาเริ่ม`;
    if (localTime(interval.start) < start || localTime(interval.end) > end) return `ช่วงยกเว้น ${i + 1} ต้องอยู่ภายใน Reference ห้ามตัดช่วง Shadow`;
  }
  const intervals = [...draft.exclusions].sort((a, b) => a.start.localeCompare(b.start));
  if (intervals.some((interval, i) => i > 0 && interval.start < intervals[i - 1].end)) return "ช่วงยกเว้นซ้อนกัน กรุณาปรับเวลาให้ไม่ทับกัน";
  return null;
}

const reasons: Record<string, string> = {
  SOURCE_PRESSURE_UNIT_UNVERIFIED: "ยังไม่ยืนยันหน่วยแรงดันต้นทาง ต้องให้ผู้ดูแลข้อมูลยืนยันหน่วยและบันทึกการตั้งค่าก่อนสร้างรอบใหม่",
  SOURCE_PRESSURE_BASIS_UNVERIFIED:"ยืนยันหน่วย psi แล้ว ยังต้องระบุว่าตัว sensor ใช้ psig (เกจ) หรือ psia (สัมบูรณ์) ไม่ต้องเปลี่ยนช่วงข้อมูลเพื่อแก้ข้อนี้",
  SOURCE_TIMEZONE_UNVERIFIED: "ยังไม่ยืนยันเขตเวลาของข้อมูลต้นทาง",
  STATE_CONTRACT_VERSION_UNVERIFIED: "ยังไม่บันทึกเวอร์ชันกติกาสถานะ Cold / Busy / SV ที่ยืนยันแล้ว",
  CONTROLLER_CODEBOOK_VERSION_UNVERIFIED: "ยังไม่บันทึกเวอร์ชันคำจำกัดความรหัสสถานะของ controller ที่ยืนยันแล้ว",
  SERVICE_EPOCH_VERSION_UNVERIFIED: "ยังไม่ยืนยันรุ่นหรือช่วงประวัติการซ่อมที่ใช้แยก baseline",
  INSUFFICIENT_CALIBRATION_COVERAGE: "Reference มีวันหรือนาทีที่ผ่าน Gate ไม่ถึงขั้นต่ำ เลือกช่วงที่มีข้อมูลเพิ่ม",
  INSUFFICIENT_RETAINED_REFERENCE_COVERAGE: "Reference หลังตัดช่วงและ Quarantine เหลือข้อมูลไม่ถึงขั้นต่ำ",
  INSUFFICIENT_SHADOW_COVERAGE: "Shadow มีข้อมูลที่ผ่าน Gate ไม่ครบ 3 วันหรือจำนวนขั้นต่ำ",
  SHADOW_SOURCE_COVERAGE_LT_95: "ข้อมูลต้นทางใน Shadow ครอบคลุมไม่ถึง 95%",
  SHADOW_DURATION_LT_REQUIRED: "ช่วงเวลาที่มีข้อมูลผ่าน Gate ใน Shadow สั้นกว่าขั้นต่ำ",
  SHADOW_DAYS_LT_REQUIRED: "Shadow มีวันข้อมูลไม่ถึงขั้นต่ำ",
  SHADOW_WINDOWS_LT_REQUIRED: "Shadow มีจำนวนนาทีไม่ถึงขั้นต่ำ",
  QUARANTINE_RATE_EXCEEDED: "Reference มีค่าที่ถูก Quarantine มากเกินเกณฑ์ ตรวจกราฟและช่วง spike",
  CALIBRATION_DRIFT_EXCEEDED: "ค่าระหว่างครึ่งแรกและครึ่งหลังของ Reference เปลี่ยนมากเกินเกณฑ์ ตรวจช่วงที่เหมาะสมกับสภาวะเดียวกัน",
  SHADOW_FLAG_RATE_EXCEEDED: "ข้อมูลช่วงทดสอบต่างจาก baseline มากกว่าเกณฑ์ ตรวจตัวแปรและช่วงเวลา อาจเป็นสภาวะเปลี่ยนหรือพฤติกรรมเครื่อง ยังไม่จำเป็นต้องเปลี่ยน Reference",
  ALL_WINDOWS_QUARANTINED: "Reference ทุกนาทีถูก Quarantine ต้องตรวจข้อมูลอ้างอิงใหม่",
  REFERENCE_SELECTION_NEEDS_REVIEW:"ระบบยังไม่พบ Reference ที่คงที่ตามเกณฑ์เสนอช่วง ต้องตรวจช่วงเปลี่ยนระดับหรือรอข้อมูลเพิ่ม การคงที่อย่างเดียวไม่ยืนยันว่าเครื่องปกติ",
  NONPOSITIVE_THRESHOLD: "ยังสร้าง threshold ที่ใช้ได้ไม่ได้ ตรวจความแปรผันของ Reference",
};
export const approvalReason = (reason: string) => reasons[reason] ?? reason;
