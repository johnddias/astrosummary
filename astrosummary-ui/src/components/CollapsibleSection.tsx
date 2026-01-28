import { useState } from 'react'

interface CollapsibleSectionProps {
  title: React.ReactNode
  defaultCollapsed?: boolean
  children: React.ReactNode
  headerRight?: React.ReactNode
}

export default function CollapsibleSection({
  title,
  defaultCollapsed = true,
  children,
  headerRight,
}: CollapsibleSectionProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed)

  return (
    <div>
      <div
        className="flex items-center justify-between cursor-pointer select-none py-1"
        onClick={() => setCollapsed(!collapsed)}
      >
        <div className="flex items-center gap-2">
          <span className="text-text-secondary text-xs w-4">
            {collapsed ? '\u25B6' : '\u25BC'}
          </span>
          <div className="font-semibold">{title}</div>
        </div>
        {headerRight && (
          <div onClick={(e) => e.stopPropagation()}>{headerRight}</div>
        )}
      </div>
      {!collapsed && <div className="mt-2">{children}</div>}
    </div>
  )
}
