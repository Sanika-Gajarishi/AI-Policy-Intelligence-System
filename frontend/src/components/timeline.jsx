import { LineChart, Line, XAxis, YAxis } from "recharts";

const data = [
  { year: 2005, policies: 2 },
  { year: 2010, policies: 5 },
  { year: 2015, policies: 8 },
  { year: 2020, policies: 12 },
];

function Timeline() {
  return (
    <LineChart width={400} height={200} data={data}>
      <XAxis dataKey="year" />
      <YAxis />
      <Line type="monotone" dataKey="policies" />
    </LineChart>
  );
}

export default Timeline;