import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  ToolboxComponent,
  BrushComponent,
  MarkAreaComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { PointForecast } from '../lib/api'
import { amount, day, time } from '../lib/api'
echarts.use([
  BarChart,
  GridComponent,
  TooltipComponent,
  ToolboxComponent,
  BrushComponent,
  MarkAreaComponent,
  CanvasRenderer,
])
interface Props {
  data: PointForecast
  selected: number
  range: [number, number] | null
  onSelect: (index: number) => void
  onRange: (range: [number, number]) => void
  rangeMode: boolean
}
export function ForecastChart({ data, selected, range, onSelect, onRange, rangeMode }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const instance = useRef<echarts.ECharts | null>(null)
  const actions = useRef({ onSelect, onRange })
  useEffect(() => {
    actions.current = { onSelect, onRange }
  }, [onSelect, onRange])
  useEffect(() => {
    if (!container.current) return
    const chart = echarts.init(container.current)
    instance.current = chart
    chart.on('click', (params) => {
      if (params.componentType === 'series') actions.current.onSelect(params.dataIndex)
    })
    chart.on('brushEnd', (event: unknown) => {
      const areas = (event as { areas?: { coordRange?: number[] }[] }).areas
      const r = areas?.[0]?.coordRange
      if (r)
        actions.current.onRange([Math.max(0, Math.round(r[0])), Math.min(24, Math.round(r[1]) + 1)])
    })
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(container.current)
    return () => {
      observer.disconnect()
      chart.dispose()
      instance.current = null
    }
  }, [])
  useEffect(() => {
    const chart = instance.current
    if (!chart) return
    chart.setOption(
      {
        animation: !window.matchMedia('(prefers-reduced-motion: reduce)').matches,
        toolbox: { show: false },
        grid: { left: 36, right: 12, top: 18, bottom: 35 },
        tooltip: {
          trigger: 'axis',
          renderMode: 'richText',
          formatter: (raw: unknown) => {
            const list = raw as { dataIndex: number }[]
            const value = data.intervals[list[0].dataIndex]
            return `${day(value.start)}\n${time(value.start)}–${time(value.end)} IST\n${amount(value.amount_mm)} mm`
          },
        },
        xAxis: {
          type: 'category',
          data: data.intervals.map((i) => time(i.start)),
          axisLine: { lineStyle: { color: '#dfe6e5' } },
          axisTick: { show: false },
          axisLabel: { color: '#7b898b', fontSize: 10, interval: 5 },
        },
        yAxis: {
          type: 'value',
          min: 0,
          minInterval: 0.1,
          axisLabel: { color: '#7b898b', fontSize: 10 },
          splitLine: { lineStyle: { color: '#edf1f0', type: 'dashed' } },
        },
        brush: {
          xAxisIndex: 0,
          brushMode: 'single',
          brushType: 'lineX',
          transformable: true,
          brushStyle: { color: 'rgba(19,119,120,.12)', borderColor: '#137778' },
        },
        series: [
          {
            type: 'bar',
            barMaxWidth: 13,
            data: data.intervals.map((i, index) => ({
              value: i.amount_mm,
              itemStyle: {
                color:
                  index === selected
                    ? '#123c42'
                    : range && index >= range[0] && index < range[1]
                      ? '#167c83'
                      : '#7ac6c8',
                borderRadius: [3, 3, 0, 0],
              },
            })),
          },
        ],
      },
      { notMerge: true },
    )
    chart.dispatchAction({
      type: 'takeGlobalCursor',
      key: 'brush',
      brushOption: { brushType: rangeMode ? 'lineX' : false, brushMode: 'single' },
    })
  }, [data, selected, range, rangeMode])
  return (
    <div
      ref={container}
      className="forecast-chart"
      role="img"
      aria-label="Three-hour precipitation bar chart. Use the timeline below for keyboard selection, or the data table for values."
    />
  )
}
