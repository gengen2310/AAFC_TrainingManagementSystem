export const AAFC_OFFICER_RANKS = [
  "PLTOFF(AAFC)",
  "FLGOFF(AAFC)",
  "FLTLT(AAFC)",
  "SQNLDR(AAFC)",
  "WGCDR(AAFC)",
  "GPCAPT(AAFC)",
  "AIRCDRE(AAFC)",
  "AVM(AAFC)",
];

export const AAFC_NCO_RANKS = [
  "LAC(AAFC)",
  "CPL(AAFC)",
  "SGT(AAFC)",
  "FSGT(AAFC)",
  "WOFF(AAFC)",
];

export const CADET_RANKS = [
  "CCPL",
  "CSGT",
  "CFSGT",
  "CWO",
  "CUO",
];

export const ALL_AAFC_RANKS = [
  ...AAFC_OFFICER_RANKS,
  ...AAFC_NCO_RANKS,
  ...CADET_RANKS,
  "CIV",
];

export function ranksForType(type: string): string[] {
  switch (type) {
    case "Officer": return AAFC_OFFICER_RANKS;
    case "NCO": return AAFC_NCO_RANKS;
    case "Senior Cadet": return CADET_RANKS;
    case "Civilian": return ["CIV"];
    default: return ALL_AAFC_RANKS;
  }
}
