import { BrowserRouter, Route, Routes } from "react-router-dom";
import { DemoProvider } from "./components/DemoContext";
import { TenantProvider } from "./components/TenantContext";
import { ThemeProvider } from "./components/ThemeContext";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import Audit from "./pages/Audit";
import Alerts from "./pages/Alerts";
import Trend from "./pages/Trend";
import ThreatAssessments from "./pages/ThreatAssessments";
import Assessments from "./pages/Assessments";
import PurviewInsights from "./pages/PurviewInsights";
import ThreatHunting from "./pages/ThreatHunting";


export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
      <DemoProvider>
      <TenantProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Overview />} />
            <Route path="audit" element={<Audit />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="threat-assessments" element={<ThreatAssessments />} />
            <Route path="assessments" element={<Assessments />} />
            <Route path="trend" element={<Trend />} />
            <Route path="purview-insights" element={<PurviewInsights />} />
            <Route path="threat-hunting" element={<ThreatHunting />} />
          </Route>
        </Routes>
      </TenantProvider>
      </DemoProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
