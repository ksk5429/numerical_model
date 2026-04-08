------- OpenFAST INPUT FILE -------------------------------------------
Gunsan 4.2MW UNISON U136 Tripod Suction Bucket OWT (OpenFAST v4 format)
---------------------- SIMULATION CONTROL --------------------------------------
False         Echo            - Echo input data to <RootName>.ech (flag)
"FATAL"       AbortLevel      - Error level when simulation should abort (string)
        120   TMax            - Total run time (s)
       0.01   DT              - Recommended module time step (s)
          1   ModCoupling     - Module coupling method (switch) {1=loose}
          2   InterpOrder     - Interpolation order (-)
          0   NumCrctn        - Number of correction iterations (-)
        0.0   RhoInf          - Numerical damping parameter (-)
       1e-4   ConvTol         - Convergence tolerance (-)
          6   MaxConvIter     - Maximum convergence iterations (-)
      99999   DT_UJac         - Time between Jacobian updates (s)
    1000000   UJacSclFact     - Scaling factor for Jacobians (-)
---------------------- FEATURE SWITCHES AND FLAGS ------------------------------
          1   NRotors         - Number of rotors (-)
          1   CompElast       - Structural dynamics {1=ElastoDyn}
          0   CompInflow      - Inflow wind {0=still air}
          0   CompAero        - Aerodynamic loads {0=None}
          0   CompServo       - Control {0=None}
          0   CompSeaSt       - Sea state {0=None}
          0   CompHydro       - Hydrodynamic loads {0=None}
          0   CompSub         - Sub-structural dynamics {0=None}
          0   CompMooring     - Mooring {0=None}
          0   CompIce         - Ice loads {0=None}
          0   CompSoil        - Soil dynamics {0=None}
          0   MHK             - MHK turbine type {0=Not MHK}
          F   MirrorRotor     - Reverse rotor rotation {F=Normal}
---------------------- ENVIRONMENTAL CONDITIONS --------------------------------
    9.80665   Gravity         - Gravitational acceleration (m/s^2)
      1.225   AirDens         - Air density (kg/m^3)
       1025   WtrDens         - Water density (kg/m^3)
  1.464E-05   KinVisc         - Kinematic viscosity (m^2/s)
        335   SpdSound        - Speed of sound (m/s)
     103500   Patm            - Atmospheric pressure (Pa)
       1700   Pvap            - Vapour pressure (Pa)
         14   WtrDpth         - Water depth (m)
          0   MSL2SWL         - MSL to SWL offset (m)
---------------------- INPUT FILES ---------------------------------------------
"Gunsan-4p2MW_ElastoDyn.dat"    EDFile          - ElastoDyn input file
"unused"      BDBldFile(1)    - BeamDyn blade 1
"unused"      BDBldFile(2)    - BeamDyn blade 2
"unused"      BDBldFile(3)    - BeamDyn blade 3
"unused"      InflowFile      - InflowWind input file
"unused"      AeroFile        - AeroDyn input file
"unused"      ServoFile       - ServoDyn input file
"unused"      SeaStFile       - SeaState input file
"unused"      HydroFile       - HydroDyn input file
"unused"      SubFile         - SubDyn input file
"unused"      MooringFile     - Mooring input file
"unused"      IceFile         - Ice input file
"unused"      SoilFile        - SoilDyn input file
---------------------- OUTPUT --------------------------------------------------
True          SumPrint        - Print summary data (flag)
         10   SttsTime        - Screen status interval (s)
      99999   ChkptTime       - Checkpoint interval (s)
    Default   DT_Out          - Output time step (s)
          0   TStart          - Start time for output (s)
          1   OutFileFmt      - Output format {1=text}
True          TabDelim        - Tab delimiters (flag)
"ES10.3E2"    OutFmt          - Output format string
---------------------- LINEARIZATION -------------------------------------------
False         Linearize       - Linearization analysis (flag)
False         CalcSteady      - Calculate steady-state (flag)
          3   TrimCase        - Trim parameter
      0.001   TrimTol         - Trim tolerance
       0.01   TrimGain        - Trim gain
          0   Twr_Kdmp        - Tower damping (N/(m/s))
          0   Bld_Kdmp        - Blade damping (N/(m/s))
          1   NLinTimes       - Number of linearization times
         60   LinTimes        - Linearization times (s)
          1   LinInputs       - Linearization inputs
          1   LinOutputs      - Linearization outputs
False         LinOutJac       - Output Jacobians (flag)
False         LinOutMod       - Module-level output (flag)
---------------------- VISUALIZATION ------------------------------------------
          0   WrVTK           - VTK output {0=none}
          2   VTK_type        - VTK type {2=meshes}
False         VTK_fields      - Write mesh fields (flag)
         15   VTK_fps         - VTK frame rate (fps)
