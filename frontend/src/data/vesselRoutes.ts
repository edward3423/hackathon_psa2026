export type Coordinate = [number, number]

export interface PlannedVessel {
  id: string
  name: string
  path: Coordinate[]
  speedKnots: number
  plan: string
  color: [number, number, number]
}

export const PLANNED_VESSELS: PlannedVessel[] = [
  {
    id: 'atlas-star',
    name: 'MV ATLAS STAR',
    path: [
      [32.3, 31.5],
      [29, 33],
      [25, 34],
      [20, 34],
      [16, 35],
      [13, 36],
      [11.8, 37],
      [11, 37.5],
      [9.5, 38],
      [5, 38],
      [0, 37],
      [-4, 36],
      [-6, 35.8],
      [-10, 35.5],
      [-15, 32],
      [-18, 28],
      [-20, 20],
      [-22, 10],
      [-20, 0],
      [-15, -15],
      [-8, -28],
      [5, -38],
      [18, -38],
      [25, -38],
      [38, -37],
      [52, -30],
      [64, -20],
      [74, -8],
      [80, 5],
      [91, 7],
      [95, 7],
      [97, 6.5],
      [98.5, 5.8],
      [100, 4],
      [102, 2],
      [103.65, 1.15],
    ],
    speedKnots: 16.2,
    plan: 'Cape reroute to Singapore',
    color: [15, 59, 255],
  },
  {
    id: 'pacific-link',
    name: 'MV PACIFIC LINK',
    path: [[139.7, 35.4], [128.1, 25.3], [121.3, 14.4], [112.1, 4.8], [103.8, 1.25]],
    speedKnots: 14.8,
    plan: 'Protected onward connection',
    color: [10, 36, 184],
  },
  {
    id: 'borneo-feeder',
    name: 'MV BORNEO FEEDER',
    path: [[119.4, -5.1], [114.1, -2.5], [108.2, 0.2], [103.8, 1.25]],
    speedKnots: 11.6,
    plan: 'Feeder arrival re-sequenced',
    color: [17, 17, 17],
  },
]
