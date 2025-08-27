import Sidebar from './components/Sidebar'
import { useApp } from './context/AppContext'
import AstroBinExport from './pages/AstroBinExport'
import RatioPlanner from './pages/RatioPlanner'
import TargetFilterReport from './pages/TargetFilterReport'

export default function App() {
  const { mode } = useApp()
  return (
    <div className="flex bg-bg-app text-text-primary min-h-screen">
      <Sidebar />
      <main className="flex-1 p-6 space-y-6">
        {mode === 'AstroBin Export' && <AstroBinExport />}
        {mode === 'Ratio Planner' && <RatioPlanner />}
        {mode === 'Target Filter Report' && <TargetFilterReport />}
      </main>
    </div>
  )
}
