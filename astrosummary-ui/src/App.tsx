import Sidebar from './components/Sidebar'
import { useApp } from './context/AppContext'
import AstroBinExport from './pages/AstroBinExport'
import TargetDataVisualizer from './pages/TargetDataVisualizer'
import NinaAnalyzer from './pages/NinaAnalyzer'
import PHD2Analyzer from './pages/PHD2Analyzer'
import RejectionValidation from './pages/RejectionValidation'

export default function App() {
  const { mode, frames, rejectionData } = useApp()
  return (
    <div className="flex bg-bg-app text-text-primary min-h-screen">
      <Sidebar />
      <main className="flex-1 p-6 space-y-6">
  {mode === 'AstroBin Export' && <AstroBinExport />}
  {mode === 'Target Data Visualizer' && <TargetDataVisualizer />}
  {mode === 'NINA Analyzer' && <NinaAnalyzer />}
  {mode === 'PHD2 Analyzer' && <PHD2Analyzer />}
  {mode === 'Rejection Validation' && <RejectionValidation frames={frames} rejectionData={rejectionData ?? null} />}
  {/* Target Filter Report moved into Target Data Visualizer view */}
      </main>
    </div>
  )
}
