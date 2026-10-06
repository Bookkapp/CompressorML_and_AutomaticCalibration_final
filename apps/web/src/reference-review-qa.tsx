// Development-only component rehearsal. Not an entry in the production build.
import { useState } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReferenceReview } from "./components/ReferenceReview";
import "./styles.css";
function Rehearsal() {
  const [module,setModule] = useState(6);
  const [reviewer,setReviewer] = useState("");
  const [batch,setBatch] = useState("");
  return <main style={{ maxWidth:1100,margin:"24px auto",padding:12 }}><h1>Reference Review · Local QA</h1><p>MX080 / M6 · actual archived source-second-derived minute caches · QA database only. No Active approval / worker / alerts.</p>
    <ReferenceReview key={module} machine="MX080" module={module} reviewer={reviewer} onReviewer={setReviewer} onModule={setModule} onBuilt={setBatch} />
    {batch && <p role="status">Candidate batch: {batch} · LOCAL ONLY / NOT ACTIVE</p>}
  </main>;
}
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient()}><Rehearsal /></QueryClientProvider>);
