import { BrowserRouter, Route, Routes } from "react-router-dom";
import { DepartmentProvider } from "./components/DepartmentContext";
import { DemoProvider } from "./components/DemoContext";
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
import DLPPolicies from "./pages/DLPPolicies";
import IRMPolicies from "./pages/IRMPolicies";
import SensitiveInfoTypes from "./pages/SensitiveInfoTypes";
import Assessments from "./pages/Assessments";


export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
      <DemoProvider>
      <DepartmentProvider>
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
            <Route path="dlp-policies" element={<DLPPolicies />} />
            <Route path="irm-policies" element={<IRMPolicies />} />
            <Route path="sensitive-info" element={<SensitiveInfoTypes />} />
            <Route path="assessments" element={<Assessments />} />
            <Route path="trend" element={<Trend />} />
          </Route>
        </Routes>
      </DepartmentProvider>
      </DemoProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
