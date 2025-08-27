export default function ChartCard(props: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-bg-card border border-slate-800 rounded-2xl p-4">
      <div className="text-sm font-medium mb-3">{props.title}</div>
      {props.children}
    </div>
  )
}
