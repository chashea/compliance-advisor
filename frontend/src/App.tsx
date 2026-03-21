import { BrowserRouter, Route, Routes } from "react-router-dom";
import { DemoProvider } from "./components/DemoContext";
import { TenantProvider } from "./components/TenantContext";
import { ThemeProvider } from "./components/ThemeContext";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import EDiscovery from "./pages/EDiscovery";
import Labels from "./pages/Labels";
import Audit from "./pages/Audit";
import DLP from "./pages/DLP";
import IRM from "./pages/IRM";
import SubjectRights from "./pages/SubjectRights";
import CommCompliance from "./pages/CommCompliance";
import Trend from "./pages/Trend";
import ThreatAssessments from "./pages/ThreatAssessments";


export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
      <DemoProvider>
      <TenantProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Overview />} />
            <Route path="ediscovery" element={<EDiscovery />} />
            <Route path="labels" element={<Labels />} />
            <Route path="audit" element={<Audit />} />
            <Route path="dlp" element={<DLP />} />
            <Route path="irm" element={<IRM />} />
            <Route path="subject-rights" element={<SubjectRights />} />
            <Route path="comm-compliance" element={<CommCompliance />} />
            <Route path="threat-assessments" element={<ThreatAssessments />} />
            <Route path="trend" element={<Trend />} />
          </Route>
        </Routes>
      </TenantProvider>
      </DemoProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
