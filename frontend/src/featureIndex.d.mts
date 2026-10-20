export type Feature={id:string;title:string;workspace:string;scope:string;evidence:string};
export const FEATURE_INDEX:readonly Feature[];
export function searchFeatures(query?:string):Feature[];
