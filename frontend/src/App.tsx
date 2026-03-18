import { BrowserRouter, Route, Routes } from "react-router-dom";
import { DepartmentProvider } from "./components/DepartmentContext";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import EDiscovery from "./pages/EDiscovery";
import Labels from "./pages/Labels";
import Audit from "./pages/Audit";
import DLP from "./pages/DLP";
import IRM from "./pages/IRM";
import SubjectRights from "./pages/SubjectRights";
import CommCompliance from "./pages/CommCompliance";
import InfoBarriers from "./pages/InfoBarriers";
import Governance from "./pages/Governance";
import Trend from "./pages/Trend";
import Advisor from "./pages/Advisor";


export default function App() {
  return (
    <BrowserRouter>
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
            <Route path="info-barriers" element={<InfoBarriers />} />
            <Route path="governance" element={<Governance />} />
            <Route path="trend" element={<Trend />} />
            <Route path="advisor" element={<Advisor />} />
          </Route>
        </Routes>
      </DepartmentProvider>
    </BrowserRouter>
  );
}
