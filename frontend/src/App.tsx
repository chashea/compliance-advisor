import { BrowserRouter, Route, Routes } from "react-router-dom";
import { DemoProvider } from "./components/DemoContext";
import { TenantProvider } from "./components/TenantContext";
import { ThemeProvider } from "./components/ThemeContext";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import EDiscovery from "./pages/EDiscovery";
import Labels from "./pages/Labels";
import Audit from "./pages/Audit";
import Alerts from "./pages/Alerts";
import CommCompliance from "./pages/CommCompliance";
import Trend from "./pages/Trend";
import ThreatAssessments from "./pages/ThreatAssessments";
import Assessments from "./pages/Assessments";


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
            <Route path="alerts" element={<Alerts />} />
            <Route path="comm-compliance" element={<CommCompliance />} />
            <Route path="threat-assessments" element={<ThreatAssessments />} />
            <Route path="assessments" element={<Assessments />} />
            <Route path="trend" element={<Trend />} />
          </Route>
        </Routes>
      </TenantProvider>
      </DemoProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
