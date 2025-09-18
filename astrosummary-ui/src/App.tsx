import Sidebar from './components/Sidebar'
import { useApp } from './context/AppContext'
import AstroBinExport from './pages/AstroBinExport'
import TargetDataVisualizer from './pages/TargetDataVisualizer'
import NinaAnalyzer from './pages/NinaAnalyzer'

export default function App() {
  const { mode } = useApp()
  return (
    <div className="flex bg-bg-app text-text-primary min-h-screen">
      <Sidebar />
      <main className="flex-1 p-6 space-y-6">
  {mode === 'AstroBin Export' && <AstroBinExport />}
  {mode === 'Target Data Visualizer' && <TargetDataVisualizer />}
  {mode === 'NINA Analyzer' && <NinaAnalyzer />}
  {/* Target Filter Report moved into Target Data Visualizer view */}
      </main>
    </div>
  )
}
