import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

interface Props {
  color: string;
  values: number[];
  labels?: string[];
  height?: number;
}

export function TrendChart({ color, values, labels, height = 150 }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    chart.setOption({
      animationDuration: 700,
      grid: { left: 8, right: 8, top: 12, bottom: 18, containLabel: true },
      tooltip: { trigger: "axis", valueFormatter: (value: unknown) => String(value) },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: labels ?? values.map((_, index) => `${index + 1}月`),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: "#8a96a8", fontSize: 10, interval: 2 }
      },
      yAxis: {
        type: "value",
        scale: true,
        splitNumber: 3,
        axisLabel: { color: "#8a96a8", fontSize: 10 },
        splitLine: { lineStyle: { color: "#edf1f6" } }
      },
      series: [
        {
          type: "line",
          data: values,
          showSymbol: false,
          smooth: 0.25,
          lineStyle: { color, width: 2.5 },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: `${color}35` },
                { offset: 1, color: `${color}02` }
              ]
            }
          }
        }
      ]
    });
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [color, labels, values]);

  return <div ref={ref} style={{ width: "100%", height }} aria-label="指标趋势图" />;
}
