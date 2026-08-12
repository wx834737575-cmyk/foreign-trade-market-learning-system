import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

interface SeriesPoint {
  period: string;
  value: number;
}

interface Props {
  m1: SeriesPoint[];
  m2: SeriesPoint[];
  height?: number;
}

export function MoneyTrendChart({ m1, m2, height = 190 }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    const periods = Array.from(new Set([...m1.map((item) => item.period), ...m2.map((item) => item.period)])).sort();
    const m1Map = new Map(m1.map((item) => [item.period, item.value]));
    const m2Map = new Map(m2.map((item) => [item.period, item.value]));
    chart.setOption({
      animationDuration: 700,
      grid: { left: 8, right: 8, top: 34, bottom: 20, containLabel: true },
      legend: { top: 0, left: 8, itemWidth: 18, textStyle: { color: "#5f6d81", fontSize: 11 } },
      tooltip: { trigger: "axis", valueFormatter: (value: unknown) => `${value}%` },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: periods.map((period) => period.slice(0, 7)),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: "#8a96a8", fontSize: 10, interval: 2 }
      },
      yAxis: {
        type: "value",
        scale: true,
        splitNumber: 3,
        axisLabel: { color: "#8a96a8", fontSize: 10, formatter: "{value}%" },
        splitLine: { lineStyle: { color: "#edf1f6" } }
      },
      series: [
        {
          name: "M2同比",
          type: "line",
          data: periods.map((period) => m2Map.get(period) ?? null),
          showSymbol: false,
          smooth: 0.2,
          lineStyle: { color: "#2777f4", width: 2.5 }
        },
        {
          name: "M1同比",
          type: "line",
          data: periods.map((period) => m1Map.get(period) ?? null),
          showSymbol: false,
          smooth: 0.2,
          lineStyle: { color: "#13a46b", width: 2.5 }
        }
      ]
    });
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [m1, m2]);

  return <div ref={ref} style={{ width: "100%", height }} aria-label="M1与M2同比趋势图" />;
}
