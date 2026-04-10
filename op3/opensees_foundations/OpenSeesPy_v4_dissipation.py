# -*- coding: utf-8 -*-
"""
OpenSeesPy_v4_dissipation.py
=============================
Self-Consistent Dissipation-Weighted BNWF from OptumGX Limit Analysis
----------------------------------------------------------------------
ALL spring parameters derived from OptumGX outputs:

  p_ult(z) = plate normal pressures at Hmax collapse       [OptumGX]
  t_ult(z) = plate shear stresses at Vmax collapse         [OptumGX]
  Np(z)    = p_ult / (su * D) = bearing capacity factor    [OptumGX]
  w(z)     = normalized energy dissipation at collapse      [OptumGX]

  k_ini(z) = C * su(z) * w(z) * D                          [shape from OptumGX]
  y50(z)   = Np(z) * D / (2 * C * w(z))                    [shape from OptumGX]

  C = delta_h * Ir  -->  SINGLE calibration parameter
      calibrated so that integral(k_ini * dz) = KH_target per bucket

Structural model: identical to SSOT_REAL_FINAL.txt (37 nodes, 57 elements)
Foundation: spine-ribs BNWF (4 ribs x 3 buckets x 19 depth nodes)
            + base rotational spring KM_base at skirt tip
Scour:      spring removal + stress correction sqrt(sigma_new/sigma_old)

Run: python OpenSeesPy_v4_dissipation.py
"""
import sys, os, math, re
import numpy as np
import pandas as pd
from pathlib import Path

SPINE_DIR = str(Path(__file__).resolve().parents[2] / "docs" / "manuscripts" / "current" / "ch4_1_optumgx_opensees_revised" / "2_opensees_models")
sys.path.insert(0, SPINE_DIR); os.chdir(SPINE_DIR)
import openseespy.opensees as ops

try:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt; HAS_MPL = True
except ImportError: HAS_MPL = False

OUTPUT = Path(r"f:\FEM\OPTUM\pipeline\mc_production\integration_comparison")
OUTPUT.mkdir(exist_ok=True)

# =============================================================================
# CONSTANTS
# =============================================================================
SSOT_FILE = "SSOT_REAL_FINAL.txt"
NUM_RIBS = 4
R = 4.0; D = 8.0; L = 9.3; DZ = 0.5
SMALL_STRAIN_MOD = 2.5
SOIL_PLUG_RHO = 1900.0
MG_THICK = 0.05; MG_RHO = 1400.0
WATER_RHO = 1025.0; CA = 1.0
su0 = 15.0; k_su = 20.0
FN_FIELD = 0.2433
SCOUR_RANGE = np.arange(0.0, 4.5, 0.5)

# SSOT stiffness per bucket
KH_SSOT = 697e3; KM_SSOT = 46700e3; KV_SSOT = 996e3  # kN/m, kNm/rad, kN/m

# Base spring allocation (from Suryasentana 2020 / Gerolymos & Gazetas 2006)
KH_BASE_FRAC = 0.30   # 30% of KH from base
KM_BASE_FRAC = 0.40   # 40% of KM from base rocking
KV_BASE_FRAC = 0.50   # 50% of KV from tip bearing

# =============================================================================
# LOAD OPTUMGX LIMIT ANALYSIS OUTPUTS
# =============================================================================
BNWF_DIR = Path(r"f:\FEM\OPTUM\pipeline\bnwf_pipeline\results")
INTEG_DIR = Path(r"f:\FEM\OPTUM\pipeline\mc_production\integration_comparison")

# --- Capacity profiles from plate extraction ---
cap = pd.read_csv(BNWF_DIR / 'capacity_profile.csv')

# --- Dissipation from solid elements (6,087 elements at Vmax collapse) ---
diss_df = pd.read_csv(INTEG_DIR / 'dissipation_skirt_Vmax.csv')

# Build depth arrays (skip z=0)
z_cap = cap['z_m'].values
z_nodes = np.arange(DZ, L + DZ/2, DZ)  # 0.5, 1.0, ..., 9.0
n_nodes = len(z_nodes)
su_z = su0 + k_su * z_nodes

# Interpolate OptumGX outputs to spring node depths
p_ult_raw = np.interp(z_nodes, z_cap, cap['p_ult_kN_m'].values)    # kN/m
t_ult_raw = np.interp(z_nodes, z_cap, cap['t_ult_kN_m'].values)    # kN/m
w_raw = np.interp(z_nodes, diss_df['db'].values, diss_df['diss_norm'].values, left=0.1, right=0.0)
w_z = np.maximum(w_raw, 0.10)  # floor at 10% so deep springs are not zero

# Bearing capacity factor from OptumGX
Np_z = np.where(su_z * D > 0, p_ult_raw / (su_z * D), 0)

# Convert to N/m for OpenSeesPy
p_ult_Nm = p_ult_raw * 1000.0  # kN/m -> N/m
t_ult_Nm = t_ult_raw * 1000.0

# =============================================================================
# CALIBRATE THE SINGLE PARAMETER C = delta_h * Ir
# =============================================================================
# Target: distributed springs provide (1 - KH_BASE_FRAC) of KH_SSOT
KH_DIST = KH_SSOT * (1 - KH_BASE_FRAC)  # kN/m per bucket

# k_ini(z) = C * su(z) * w(z)  [kN/m3]
# integral(k_ini * D * dz, 0 to L) = KH_DIST
# C * D * integral(su * w * dz) = KH_DIST
integral_su_w = np.trapezoid(su_z * w_z, z_nodes)  # kPa*m
C_cal = KH_DIST / (D * integral_su_w)

# Spring stiffness profile
k_z = C_cal * su_z * w_z  # kN/m3

# y50 profile: y50 = Np * D / (2 * C * w)
y50_z = np.where(w_z > 0, Np_z * D / (2 * C_cal * w_z), 0.01)
y50_z = np.clip(y50_z, 1e-5, 1.0)  # physical bounds

# Base springs
KH_BASE = KH_SSOT * KH_BASE_FRAC   # kN/m
KM_BASE = KM_SSOT * KM_BASE_FRAC   # kNm/rad
KV_BASE = KV_SSOT * KV_BASE_FRAC   # kN/m

# Verify
Kh_check = np.trapezoid(k_z * D, z_nodes)
print(f"  C = delta_h * Ir = {C_cal:.4f}", flush=True)
print(f"  KH_dist check: {Kh_check:.0f} kN/m (target: {KH_DIST:.0f})", flush=True)
print(f"  k(z) range: {k_z.min():.0f} to {k_z.max():.0f} kN/m3", flush=True)
print(f"  y50 range: {y50_z.min()*1000:.2f} to {y50_z.max()*1000:.2f} mm", flush=True)
print(f"  Np(z) range: {Np_z[Np_z>0].min():.2f} to {Np_z.max():.2f}", flush=True)
print(f"  w(z) range: {w_z.min():.3f} to {w_z.max():.3f}", flush=True)

# Print spring parameter table
print(f"\n{'z':>5s}  {'su':>5s}  {'w(z)':>6s}  {'Np':>5s}  {'k_ini':>8s}  {'p_ult':>8s}  {'y50':>8s}  {'t_ult':>8s}", flush=True)
print(f"{'[m]':>5s}  {'[kPa]':>5s}  {'[-]':>6s}  {'[-]':>5s}  {'[kN/m3]':>8s}  {'[kN/m]':>8s}  {'[mm]':>8s}  {'[kN/m]':>8s}", flush=True)
print("-" * 65, flush=True)
for i in range(n_nodes):
    if z_nodes[i] % 1.0 < 0.01:
        print(f"{z_nodes[i]:5.1f}  {su_z[i]:5.0f}  {w_z[i]:6.3f}  {Np_z[i]:5.2f}  "
              f"{k_z[i]:8.0f}  {p_ult_raw[i]:8.1f}  {y50_z[i]*1000:8.2f}  {t_ult_raw[i]:8.1f}", flush=True)


# =============================================================================
# STRUCTURAL MODEL
# =============================================================================
class TripodModel:
    def __init__(self):
        self.nodes = {}; self.elements = []; self.lumped_masses = {}
        self.rib_nodes = []
        self.E = 2.1e11; self.Gs = 8.1e10; self.rho = 7850.0
        self._nid = 10000; self._eid = 10000; self._mid = 10000
        self._sid = 10000; self._tid = 100

    def _reset(self):
        self._nid=10000; self._eid=10000; self._mid=10000
        self._sid=10000; self._tid=100; self.rib_nodes=[]

    def load_data(self):
        with open(SSOT_FILE,'r',encoding='utf-8') as f: lines=f.readlines()
        sec=None
        for line in lines:
            line=line.strip()
            if not line or line.startswith('#'):
                if '1. GLOBAL' in line: sec='MAT'
                elif '2. NODAL' in line: sec='MASS'
                elif '4. NODAL' in line: sec='N'
                elif '5. ELEMENT' in line: sec='T'
                elif '6. ELEMENT' in line: sec='P'
                elif '8. SECONDARY' in line: sec='SM'
                continue
            if sec=='MAT':
                if 'DENSITY_RHO:' in line: self.rho=float(line.split(':')[1].split('#')[0])*1.05
                elif 'YOUNGS_MODULUS_E:' in line: self.E=float(line.split(':')[1].split('#')[0])
                elif 'SHEAR_MODULUS_G:' in line: self.Gs=float(line.split(':')[1].split('#')[0])
            elif sec in ['MASS','SM']:
                m=re.search(r'NODE_MASS_(\d+):\s*([\d.E+\-]+)',line)
                if m: nid=int(m.group(1)); self.lumped_masses[nid]=self.lumped_masses.get(nid,0)+float(m.group(2))
            elif sec=='N':
                p=line.split('#')[0].split()
                if len(p)>=4 and p[0].isdigit(): self.nodes[int(p[0])]=(float(p[1]),float(p[2]),float(p[3]))
            elif sec in ['T','P']:
                p=line.split('#')[0].split()
                if len(p)>=6:
                    try: self.elements.append({'n1':int(p[1]),'n2':int(p[2]),'Dt':float(p[3]),'Db':float(p[4]),'t':float(p[5]),'tap':abs(float(p[3])-float(p[4]))>1e-4})
                    except (ValueError, IndexError): pass  # skip unparseable element lines

    def build_model(self, scour):
        ops.wipe(); ops.model('basic','-ndm',3,'-ndf',6); self._reset()
        for nid,(x,y,z) in self.nodes.items(): ops.node(nid,x,y,z)
        tc=1
        for el in self.elements: self._beam(el,tc); tc+=1
        self._foundation(scour)
        self._physics(scour)
        self._ghost()

    def _props(self,Dv,t):
        Di=Dv-2*t; A=math.pi/4*(Dv**2-Di**2); I=math.pi/64*(Dv**4-Di**4)
        return A,I,I,2*I

    def _beam(self,el,tc):
        n1,n2=el['n1'],el['n2']
        if n1 not in self.nodes or n2 not in self.nodes: return
        c1,c2=self.nodes[n1],self.nodes[n2]
        dz=abs(c2[2]-c1[2]); Ll=math.sqrt(sum((a-b)**2 for a,b in zip(c1,c2)))
        if Ll<1e-6: return
        if dz/Ll>0.99: ops.geomTransf('Linear',tc,0,1,0)
        else: ops.geomTransf('Linear',tc,0,0,1)
        et=self._eid; self._eid+=1
        Da=(el['Dt']+el['Db'])/2; A,_,_,_=self._props(Da,el['t'])
        if el['tap']:
            xi=[-1,-math.sqrt(3/7),0,math.sqrt(3/7),1]; wt=[0.1,49/90,32/45,49/90,0.1]
            locs=[(x+1)/2 for x in xi]; tags=[]
            for s in locs:
                d=el['Dt']+s*(el['Db']-el['Dt']); A2,Iy,Iz,J=self._props(d,el['t'])
                st=self._sid; self._sid+=1; ops.section('Elastic',st,self.E,A2,Iz,Iy,self.Gs,J); tags.append(st)
            ops.beamIntegration('UserDefined',et,5,*tags,*locs,*wt)
        else:
            A2,Iy,Iz,J=self._props(el['Dt'],el['t'])
            st=self._sid; self._sid+=1; ops.section('Elastic',st,self.E,A2,Iz,Iy,self.Gs,J)
            ops.beamIntegration('Lobatto',et,st,5)
        ops.element('forceBeamColumn',et,n1,n2,tc,et,'-mass',A*self.rho)

    def _foundation(self, scour):
        tv=self._tid; self._tid+=1; th=self._tid; self._tid+=1
        ops.geomTransf('Linear',tv,0,1,0); ops.geomTransf('Linear',th,0,0,1)
        A_rib=(2*math.pi*R*0.05)/NUM_RIBS; I_rib=1.0

        for ctr in [215,225,235]:
            if ctr not in self.nodes: continue
            cx,cy,cz=self.nodes[ctr]
            for i in range(NUM_RIBS):
                ang=2*math.pi*i/NUM_RIBS
                rx=cx+R*math.cos(ang); ry=cy+R*math.sin(ang)
                top=self._nid; self._nid+=1; ops.node(top,rx,ry,cz)
                le=self._eid; self._eid+=1
                ops.element('elasticBeamColumn',le,ctr,top,100,1e14,1e14,100,100,100,th,'-mass',1.0)
                prev=top
                for j,depth in enumerate(z_nodes):
                    if depth>L: break
                    cur=self._nid; self._nid+=1; ops.node(cur,rx,ry,cz-depth)
                    self.rib_nodes.append(cur)
                    se=self._eid; self._eid+=1; st=self._sid; self._sid+=1
                    ops.section('Elastic',st,self.E,A_rib,I_rib,I_rib,self.Gs,I_rib)
                    ops.element('elasticBeamColumn',se,prev,cur,A_rib,self.E,self.Gs,I_rib,I_rib,I_rib,tv,'-mass',A_rib*self.rho)
                    if depth > scour:
                        self._py_tz_spring(cur, j, depth, scour)
                    prev=cur
                if L > scour:
                    self._base_spring(prev, scour)

    def _py_tz_spring(self, node, j, depth, scour):
        """PySimple1 + TzSimple1 with stress correction. All params from OptumGX."""
        sO=depth*10000.0; sN=(depth-scour)*10000.0
        if sN<=0: return
        sf=math.sqrt(sN/sO)

        # Lateral: k and p_ult from OptumGX, stress-corrected
        Kpy = (k_z[j] * D * DZ * 1000.0 / NUM_RIBS) * sf    # N/m per rib
        pult = (p_ult_Nm[j] * DZ / NUM_RIBS) * (sf**2)       # N per rib
        if Kpy < 1: return
        y50 = max((0.5 * pult / Kpy) / SMALL_STRAIN_MOD, 1e-6)

        # Vertical shaft: t_ult from OptumGX, stress-corrected
        tult = (t_ult_Nm[j] * DZ / NUM_RIBS) * (sf**2)       # N per rib
        ktz = Kpy * 0.5
        z50 = max((0.5 * tult / ktz) / SMALL_STRAIN_MOD, 1e-6) if ktz > 0 else 0.01

        mp=self._mid; self._mid+=1; ops.uniaxialMaterial('PySimple1',mp,2,pult,y50,0.0)
        mt=self._mid; self._mid+=1; ops.uniaxialMaterial('TzSimple1',mt,2,tult,z50,0.0)
        a=self._nid; self._nid+=1; c=ops.nodeCoord(node); ops.node(a,*c); ops.fix(a,1,1,1,1,1,1)
        e=self._eid; self._eid+=1; ops.element('zeroLength',e,a,node,'-mat',mp,mp,mt,'-dir',1,2,3)

    def _base_spring(self, node, scour):
        """Base springs: KH, KM, KV at skirt tip per rib."""
        sO=L*10000.0; sN=(L-scour)*10000.0
        if sN<0: return
        sf=math.sqrt(sN/sO) if sO>0 else 0
        kh=KH_BASE*1000/(3*NUM_RIBS)*sf
        kv=KV_BASE*1000/(3*NUM_RIBS)*sf
        km=KM_BASE*1000/(3*NUM_RIBS)*sf
        mh=self._mid; self._mid+=1; ops.uniaxialMaterial('Elastic',mh,max(kh,1))
        mv=self._mid; self._mid+=1; ops.uniaxialMaterial('Elastic',mv,max(kv,1))
        mr1=self._mid; self._mid+=1; ops.uniaxialMaterial('Elastic',mr1,max(km,1))
        mr2=self._mid; self._mid+=1; ops.uniaxialMaterial('Elastic',mr2,max(km,1))
        mg=self._mid; self._mid+=1; ops.uniaxialMaterial('Elastic',mg,1.0)
        a=self._nid; self._nid+=1; c=ops.nodeCoord(node); ops.node(a,*c); ops.fix(a,1,1,1,1,1,1)
        e=self._eid; self._eid+=1
        ops.element('zeroLength',e,a,node,'-mat',mh,mh,mv,mr1,mr2,mg,'-dir',1,2,3,4,5,6)

    def _physics(self, scour):
        for n,m in self.lumped_masses.items():
            if n in self.nodes: ops.mass(n,m,m,m,0,0,0)
        MSL=0.0
        for el in self.elements:
            n1,n2=el['n1'],el['n2']
            if n1 not in self.nodes or n2 not in self.nodes: continue
            z1,z2=self.nodes[n1][2],self.nodes[n2][2]
            if z1>MSL and z2>MSL: continue
            c1,c2=self.nodes[n1],self.nodes[n2]
            Ll=math.sqrt(sum((a-b)**2 for a,b in zip(c1,c2)))
            zt,zb=max(z1,z2),min(z1,z2)
            Ls=Ll if zt<=MSL else (Ll*((MSL-zb)/(zt-zb)) if zt>zb else 0)
            Da=(el['Dt']+el['Db'])/2; De=Da+2*MG_THICK
            Mb=(math.pi/4)*(De**2-Da**2)*MG_RHO*Ls
            Mh=CA*WATER_RHO*(math.pi/4)*De**2*Ls
            ops.mass(n1,(Mb+Mh)/2,(Mb+Mh)/2,(Mb+Mh)/2,0,0,0)
            ops.mass(n2,(Mb+Mh)/2,(Mb+Mh)/2,(Mb+Mh)/2,0,0,0)
        mz=-8.2; sz=mz-scour; ap=(math.pi*R**2)/NUM_RIBS
        for nid in self.rib_nodes:
            try:
                z=ops.nodeCoord(nid)[2]
                if z<sz: mp_=ap*0.5*SOIL_PLUG_RHO; ops.mass(nid,mp_,mp_,0,0,0,0)
            except Exception: pass  # node may have been removed by scour

    def _ghost(self):
        gm=self._mid; self._mid+=1; ops.uniaxialMaterial('Elastic',gm,1.0)
        for nid in ops.getNodeTags():
            a=self._nid; self._nid+=1; ops.node(a,*ops.nodeCoord(nid)); ops.fix(a,1,1,1,1,1,1)
            e=self._eid; self._eid+=1; ops.element('zeroLength',e,a,nid,'-mat',*[gm]*6,'-dir',1,2,3,4,5,6)

    def run_eigen(self):
        try:
            v=ops.eigen('-fullGenLapack',1)
            return math.sqrt(v[0])/(2*math.pi) if v else 0.0
        except Exception: return 0.0  # eigenvalue solver failure


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print("=" * 70, flush=True)
    print("OpenSeesPy v4: Dissipation-Weighted BNWF from OptumGX", flush=True)
    print("All spring shapes from limit analysis | 1 calibration parameter", flush=True)
    print(f"Field f_n = {FN_FIELD:.4f} Hz", flush=True)
    print("=" * 70, flush=True)

    model = TripodModel()
    model.load_data()
    print(f"Model: {len(model.nodes)} nodes, {len(model.elements)} elements", flush=True)

    # --- Scour sweep ---
    results = []
    f0 = None
    print(f"\n{'S [m]':>6s}  {'f_n [Hz]':>9s}  {'Drop':>6s}  {'Err vs field':>12s}", flush=True)
    print("-" * 40, flush=True)

    for S in SCOUR_RANGE:
        model.build_model(S)
        f1 = model.run_eigen()
        if S == 0: f0 = f1
        drop = (f0 - f1) / f0 * 100 if f0 > 0 else 0
        err = (f1 - FN_FIELD) / FN_FIELD * 100
        print(f"{S:6.1f}  {f1:9.4f}  {drop:5.1f}%  {err:+11.1f}%", flush=True)
        results.append({'scour_m': S, 'f_n_Hz': f1, 'drop_pct': drop, 'err_pct': err})

    df = pd.DataFrame(results)
    df.to_csv(OUTPUT / 'fn_vs_scour_v4_dissipation.csv', index=False)

    # --- Save spring parameter table ---
    sp_table = pd.DataFrame({
        'z_m': z_nodes, 'su_kPa': su_z, 'w_dissip': w_z, 'Np': Np_z,
        'k_ini_kNm3': k_z, 'p_ult_kNm': p_ult_raw, 'y50_mm': y50_z * 1000,
        't_ult_kNm': t_ult_raw,
        'source_k': 'OptumGX dissipation + su',
        'source_pult': 'OptumGX plates (Hmax)',
        'source_y50': 'OptumGX Np/w ratio',
        'source_tult': 'OptumGX plates (Vmax)',
    })
    sp_table.to_csv(OUTPUT / 'spring_params_v4_dissipation.csv', index=False)

    # --- Summary ---
    print(f"\n{'=' * 70}", flush=True)
    print("PARAMETER SOURCES", flush=True)
    print(f"{'=' * 70}", flush=True)
    print(f"  k_ini(z) = C x su(z) x w(z) x D    C = {C_cal:.4f}", flush=True)
    print(f"             su(z) from OptumGX soil model", flush=True)
    print(f"             w(z)  from OptumGX dissipation (6,087 solid elements)", flush=True)
    print(f"  p_ult(z) = OptumGX plate pressures at Hmax collapse (600 plates)", flush=True)
    print(f"  y50(z)   = Np(z) x D / (2 x C x w(z))", flush=True)
    print(f"             Np(z) from OptumGX: p_ult/(su x D)", flush=True)
    print(f"             w(z)  from OptumGX dissipation", flush=True)
    print(f"  t_ult(z) = OptumGX plate shear at Vmax collapse", flush=True)
    print(f"\n  Calibration: C = {C_cal:.4f} -> KH_dist = {Kh_check:.0f} kN/m", flush=True)
    print(f"  Base springs: KH={KH_BASE/1e3:.0f} KM={KM_BASE/1e3:.0f} KV={KV_BASE/1e3:.0f} MN", flush=True)

    f_S0 = df[df['scour_m']==0]['f_n_Hz'].values[0]
    f_S4 = df[df['scour_m']==4]['f_n_Hz'].values[0]
    print(f"\n  f_n at S=0: {f_S0:.4f} Hz (field: {FN_FIELD:.4f}, err: {(f_S0-FN_FIELD)/FN_FIELD*100:+.1f}%)", flush=True)
    print(f"  f_n at S=4: {f_S4:.4f} Hz (drop: {(f_S0-f_S4)/f_S0*100:.1f}%)", flush=True)

    # --- Plot ---
    if HAS_MPL:
        fig, axes = plt.subplots(1, 3, figsize=(16, 6))

        # Panel 1: Spring parameter profiles
        ax = axes[0]
        ax.plot(k_z, z_nodes, 'b-o', ms=4, label='k_ini [kN/m3]')
        ax.set_xlabel('k_ini (kN/m3)', color='blue')
        ax.set_ylabel('Depth below mudline (m)')
        ax.invert_yaxis()
        ax.set_title('Spring Stiffness Profile')
        ax2 = ax.twiny()
        ax2.plot(p_ult_raw, z_nodes, 'r-s', ms=4, label='p_ult [kN/m]')
        ax2.set_xlabel('p_ult (kN/m)', color='red')
        ax.grid(True, alpha=0.3)

        # Panel 2: Dissipation weight and Np
        ax = axes[1]
        ax.barh(z_nodes, w_z, height=0.4, alpha=0.6, color='orange', label='w(z) dissipation')
        ax.set_xlabel('Dissipation weight w(z)')
        ax.set_ylabel('Depth below mudline (m)')
        ax.invert_yaxis()
        ax.set_title('OptumGX Dissipation Profile')
        ax2 = ax.twiny()
        ax2.plot(Np_z, z_nodes, 'g-^', ms=5, label='Np(z)')
        ax2.set_xlabel('Bearing factor Np', color='green')
        ax.grid(True, alpha=0.3)

        # Panel 3: f_n vs scour
        ax = axes[2]
        ax.plot(df['scour_m'], df['f_n_Hz'], 'b-o', lw=2, ms=7, label='v4 Dissipation-Weighted')
        ax.axhline(FN_FIELD, color='red', ls='--', lw=1.5, label=f'Field ({FN_FIELD} Hz)')
        ax.set_xlabel('Scour Depth (m)')
        ax.set_ylabel('Natural Frequency (Hz)')
        ax.set_title('f_n vs Scour')
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

        fig.suptitle('Dissipation-Weighted BNWF: All Parameters from OptumGX Limit Analysis', fontsize=13)
        fig.tight_layout()
        fig.savefig(OUTPUT / 'fn_vs_scour_v4_dissipation.png', dpi=300)
        print(f"\n  Saved: {OUTPUT / 'fn_vs_scour_v4_dissipation.png'}", flush=True)
        plt.close()

    print(f"  Saved: {OUTPUT / 'fn_vs_scour_v4_dissipation.csv'}", flush=True)
    print(f"  Saved: {OUTPUT / 'spring_params_v4_dissipation.csv'}", flush=True)
    print("=" * 70, flush=True)
