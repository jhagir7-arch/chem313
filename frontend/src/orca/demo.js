// Deliberately synthetic fixtures: these are interface examples, not research results.
export function demoText(offset=0) {return `                         * O   R   C   A *
Program Version 6.1.0
INPUT FILE
|  1> ! B3LYP def2-SVP Opt Freq
Total Charge ... 0
Multiplicity ... 1
CARTESIAN COORDINATES (ANGSTROEM)
---------------------------------
O    0.000000   0.000000   0.000000
H    0.758602   0.000000   0.504284
H   -0.758602   0.000000   0.504284

SCF CONVERGED AFTER 8 CYCLES
FINAL SINGLE POINT ENERGY     ${-76.123456789 + offset}
THE OPTIMIZATION HAS CONVERGED
VIBRATIONAL FREQUENCIES
-----------------------
0: 0.00 cm**-1
1: 0.00 cm**-1
2: 0.00 cm**-1
3: 0.00 cm**-1
4: 0.00 cm**-1
5: 0.00 cm**-1
6: 1595.20 cm**-1
7: 3657.10 cm**-1
8: 3755.90 cm**-1
NORMAL MODES
THERMOCHEMISTRY
Temperature ... 298.15 K
Zero point energy ... 0.020500 Eh
Total Enthalpy ... ${-76.100000 + offset} Eh
Final Gibbs free energy ... ${-76.121000 + offset} Eh
****ORCA TERMINATED NORMALLY****
`;}
