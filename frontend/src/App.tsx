import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import { NewJobPage } from './components/pages/NewJobPage'
import { WizardPage } from './components/pages/WizardPage'
import { JobsPage } from './components/pages/JobsPage'
import { JobDetailPage } from './components/pages/JobDetailPage'
import { MediaPage } from './components/pages/MediaPage'
import { SettingsPage } from './components/pages/SettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<WizardPage />} />
          <Route path="new" element={<NewJobPage />} />
          <Route path="jobs" element={<JobsPage />} />
          <Route path="jobs/:id" element={<JobDetailPage />} />
          <Route path="media" element={<MediaPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
