import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from './components/Layout'
import Stub from './components/Stub'
import DashboardPage from './modules/dashboard/DashboardPage'
import ComptesPage from './modules/comptes/ComptesPage'
import PersonasPage from './modules/personas/PersonasPage'
import PostingPage from './modules/posting/PostingPage'
import VeillePage from './modules/veille/VeillePage'
import StatistiquesPage from './modules/statistiques/StatistiquesPage'
import CrmPage from './modules/crm/CrmPage'
import LiensPage from './modules/liens/LiensPage'
import LogsPage from './modules/logs/LogsPage'
import TargetsPage from './modules/targets/TargetsPage'
import ScenariosPage from './modules/scenarios/ScenariosPage'
import ComportementsPage from './modules/comportements/ComportementsPage'
import ProxiesPage from './modules/proxies/ProxiesPage'
import ParcIphonePage from './modules/parc-iphone/ParcIphonePage'
import ParametresPage from './modules/parametres/ParametresPage'

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } },
})

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/comptes" element={<ComptesPage />} />
            <Route path="/personas" element={<PersonasPage />} />
            <Route path="/posting" element={<PostingPage />} />
            <Route path="/veille" element={<VeillePage />} />
            <Route path="/statistiques" element={<StatistiquesPage />} />
            <Route path="/crm" element={<CrmPage />} />
            <Route path="/liens" element={<LiensPage />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/targets" element={<TargetsPage />} />
            <Route path="/scenarios" element={<ScenariosPage />} />
            <Route path="/comportements" element={<ComportementsPage />} />
            <Route path="/proxies" element={<ProxiesPage />} />
            <Route path="/parc" element={<ParcIphonePage />} />
            <Route path="/parametres" element={<ParametresPage />} />
            <Route path="*" element={<Stub name="Page introuvable" />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
