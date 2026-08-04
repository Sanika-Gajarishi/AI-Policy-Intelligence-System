import { LineChart, Line, XAxis, YAxis, Tooltip } from "recharts";

const data = [
  { year: 2005, policies: 2 },
  { year: 2010, policies: 5 },
  { year: 2015, policies: 8 },
  { year: 2020, policies: 12 },
];

export default function ChartComponent() {
  return (
    <div className="bg-white p-5 rounded-2xl shadow mb-6">
      <h2 className="text-xl font-semibold mb-3">Policy Trends 📊</h2>

      <LineChart width={400} height={200} data={data}>
        <XAxis dataKey="year" />
        <YAxis />
        <Tooltip />
        <Line type="monotone" dataKey="policies" />
      </LineChart>
    </div>
  );
}