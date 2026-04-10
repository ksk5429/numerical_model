# -*- coding: utf-8 -*-
"""
OpenSeesPy_v6_three_analyses.py
================================
Three Analysis Modes Using the Generalized Vesic-Wolf-Gazetas Framework
------------------------------------------------------------------------
All foundation springs derived from OptumGX limit analysis outputs.

Analysis 1: EIGENVALUE  → f_n vs scour (validates k_ini from dissipation)
Analysis 2: PUSHOVER    → H_collapse vs OptumGX Hmax (validates p_ult, y50)
Analysis 3: TRANSIENT   → Free vibration decay (validates dashpot from w(z))

Foundation: dissipation-weighted BNWF + base springs
  Tier 1: k(z) = C*su*w(z), p_ult from OptumGX, y50 = Np*D/(2Cw)
  Tier 2: c_rad(z) = rho*Vs*A_eff*w(z)  [radiation dashpot]
  Tier 3: c_mat(z) = 2*k*beta_0/omega    [material dashpot]

Run: python OpenSeesPy_v6_three_analyses.py
"""
import sys, os, math, re, time
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

# =============================================================================
# CONSTANTS AND OPTUMGX DATA (same as v4/v5)
# =============================================================================
SSOT_FILE = "SSOT_REAL_FINAL.txt"
NUM_RIBS = 4; R = 4.0; D = 8.0; L = 9.3; DZ = 0.5
SMALL_STRAIN_MOD = 2.5
SOIL_PLUG_RHO = 1900.0; MG_THICK = 0.05; MG_RHO = 1400.0
WATER_RHO = 1025.0; CA = 1.0
su0 = 15.0; k_su = 20.0
FN_FIELD = 0.2433
rho_soil = 1850.0; Vs = 69.0; beta_0 = 0.04
KH_SSOT = 697e3; KM_SSOT = 46700e3; KV_SSOT = 996e3
KH_BASE_FRAC = 0.30; KM_BASE_FRAC = 0.40; KV_BASE_FRAC = 0.50

# OptumGX reference capacities (full model, from MC production)
HMAX_OPTUMGX = 24853 * 2  # kN (half-model x2 = 49706 kN full)
VMAX_OPTUMGX = 58533 * 2  # kN

BNWF_DIR = Path(r"f:\FEM\OPTUM\pipeline\bnwf_pipeline\results")
INTEG_DIR = Path(r"f:\FEM\OPTUM\pipeline\mc_production\integration_comparison")

cap = pd.read_csv(BNWF_DIR / 'capacity_profile.csv')
diss_df = pd.read_csv(INTEG_DIR / 'dissipation_skirt_Vmax.csv')

z_nodes = np.arange(DZ, L + DZ/2, DZ)
su_z = su0 + k_su * z_nodes
p_ult_raw = np.interp(z_nodes, cap['z_m'].values, cap['p_ult_kN_m'].values)
t_ult_raw = np.interp(z_nodes, cap['z_m'].values, cap['t_ult_kN_m'].values)
w_z = np.interp(z_nodes, diss_df['db'].values, diss_df['diss_norm'].values, left=0.1, right=0.0)
w_z = np.maximum(w_z, 0.10)
Np_z = np.where(su_z * D > 0, p_ult_raw / (su_z * D), 0)
p_ult_Nm = p_ult_raw * 1000.0; t_ult_Nm = t_ult_raw * 1000.0

KH_DIST = KH_SSOT * (1 - KH_BASE_FRAC)
C_cal = KH_DIST / (D * np.trapezoid(su_z * w_z, z_nodes))
k_z = C_cal * su_z * w_z
KH_BASE = KH_SSOT * KH_BASE_FRAC
KM_BASE = KM_SSOT * KM_BASE_FRAC
KV_BASE = KV_SSOT * KV_BASE_FRAC
omega_n = 2 * math.pi * FN_FIELD

print(f"  C = {C_cal:.2f}, HMAX_OptumGX = {HMAX_OPTUMGX:.0f} kN (full model)", flush=True)


# =============================================================================
# STRUCTURAL MODEL (reusable for all 3 analyses)
# =============================================================================
class TripodModel:
    def __init__(self):
        self.nodes = {}; self.elements = []; self.lumped_masses = {}
        self.rib_nodes = []; self.hub_node = None
        self.E = 2.1e11; self.Gs = 8.1e10; self.rho = 7850.0
        self._nid=10000; self._eid=10000; self._mid=10000; self._sid=10000; self._tid=100

    def _reset(self):
        self._nid=10000; self._eid=10000; self._mid=10000; self._sid=10000; self._tid=100
        self.rib_nodes=[]

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
        # Find hub (topmost node)
        max_z = -1e10
        for nid, (x,y,z) in self.nodes.items():
            if z > max_z: max_z = z; self.hub_node = nid

    def build(self, scour, dashpot=False):
        ops.wipe(); ops.model('basic','-ndm',3,'-ndf',6); self._reset()
        self._dashpot = dashpot
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
        A_rib=(2*math.pi*R*0.05)/NUM_RIBS
        for ctr in [215,225,235]:
            if ctr not in self.nodes: continue
            cx,cy,cz=self.nodes[ctr]
            for i in range(NUM_RIBS):
                ang=2*math.pi*i/NUM_RIBS; rx=cx+R*math.cos(ang); ry=cy+R*math.sin(ang)
                top=self._nid; self._nid+=1; ops.node(top,rx,ry,cz)
                le=self._eid; self._eid+=1
                ops.element('elasticBeamColumn',le,ctr,top,100,1e14,1e14,100,100,100,th,'-mass',1.0)
                prev=top
                for j,depth in enumerate(z_nodes):
                    if depth>L: break
                    cur=self._nid; self._nid+=1; ops.node(cur,rx,ry,cz-depth)
                    self.rib_nodes.append(cur)
                    se=self._eid; self._eid+=1; st=self._sid; self._sid+=1
                    ops.section('Elastic',st,self.E,A_rib,1.0,1.0,self.Gs,1.0)
                    ops.element('elasticBeamColumn',se,prev,cur,A_rib,self.E,self.Gs,1.0,1.0,1.0,tv,'-mass',A_rib*self.rho)
                    if depth > scour:
                        self._spring(cur, j, depth, scour)
                    prev=cur
                if L > scour:
                    self._base(prev, scour)

    def _spring(self, node, j, depth, scour):
        sO=depth*10000; sN=(depth-scour)*10000
        if sN<=0: return
        sf=math.sqrt(sN/sO)
        Kpy=(k_z[j]*D*DZ*1000/NUM_RIBS)*sf
        pult=(p_ult_Nm[j]*DZ/NUM_RIBS)*(sf**2)
        if Kpy<1: return
        y50=max((0.5*pult/Kpy)/SMALL_STRAIN_MOD, 1e-6)
        tult=(t_ult_Nm[j]*DZ/NUM_RIBS)*(sf**2)
        ktz=Kpy*0.5; z50=max((0.5*tult/ktz)/SMALL_STRAIN_MOD,1e-6) if ktz>0 else 0.01

        anc=self._nid; self._nid+=1; c=ops.nodeCoord(node); ops.node(anc,*c); ops.fix(anc,1,1,1,1,1,1)

        if not self._dashpot:
            mp=self._mid; self._mid+=1; ops.uniaxialMaterial('PySimple1',mp,2,pult,y50,0.0)
            mt=self._mid; self._mid+=1; ops.uniaxialMaterial('TzSimple1',mt,2,tult,z50,0.0)
            el=self._eid; self._eid+=1; ops.element('zeroLength',el,anc,node,'-mat',mp,mp,mt,'-dir',1,2,3)
        else:
            # Spring + dashpot in parallel
            ms=self._mid; self._mid+=1; ops.uniaxialMaterial('PySimple1',ms,2,pult,y50,0.0)
            A_eff=math.pi*D*DZ
            c_rad=rho_soil*Vs*A_eff*w_z[j]/NUM_RIBS*sf
            c_mat=2*Kpy*beta_0/omega_n if omega_n>0 else 0
            md=self._mid; self._mid+=1; ops.uniaxialMaterial('Viscous',md,c_rad+c_mat,1.0)
            mp=self._mid; self._mid+=1; ops.uniaxialMaterial('Parallel',mp,ms,md)
            # Vertical
            mts=self._mid; self._mid+=1; ops.uniaxialMaterial('TzSimple1',mts,2,tult,z50,0.0)
            mtd=self._mid; self._mid+=1; ops.uniaxialMaterial('Viscous',mtd,(c_rad+c_mat)*0.5,1.0)
            mt=self._mid; self._mid+=1; ops.uniaxialMaterial('Parallel',mt,mts,mtd)
            el=self._eid; self._eid+=1; ops.element('zeroLength',el,anc,node,'-mat',mp,mp,mt,'-dir',1,2,3)

    def _base(self, node, scour):
        sO=L*10000; sN=(L-scour)*10000
        if sN<0: return
        sf=math.sqrt(sN/sO) if sO>0 else 0
        kh=KH_BASE*1000/(3*NUM_RIBS)*sf; kv=KV_BASE*1000/(3*NUM_RIBS)*sf; km=KM_BASE*1000/(3*NUM_RIBS)*sf
        mh=self._mid; self._mid+=1; ops.uniaxialMaterial('Elastic',mh,max(kh,1))
        mv=self._mid; self._mid+=1; ops.uniaxialMaterial('Elastic',mv,max(kv,1))
        mr1=self._mid; self._mid+=1; ops.uniaxialMaterial('Elastic',mr1,max(km,1))
        mr2=self._mid; self._mid+=1; ops.uniaxialMaterial('Elastic',mr2,max(km,1))
        mg=self._mid; self._mid+=1; ops.uniaxialMaterial('Elastic',mg,1.0)
        a=self._nid; self._nid+=1; c=ops.nodeCoord(node); ops.node(a,*c); ops.fix(a,1,1,1,1,1,1)
        e=self._eid; self._eid+=1; ops.element('zeroLength',e,a,node,'-mat',mh,mh,mv,mr1,mr2,mg,'-dir',1,2,3,4,5,6)

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
# ANALYSIS 1: EIGENVALUE (f_n vs scour)
# =============================================================================
def run_eigenvalue(model):
    print("\n" + "="*70, flush=True)
    print("ANALYSIS 1: EIGENVALUE (f_n vs scour)", flush=True)
    print("  Tests: k_ini(z) from dissipation-weighted framework", flush=True)
    print("="*70, flush=True)
    results = []
    f0 = None
    for S in np.arange(0, 4.5, 0.5):
        model.build(S, dashpot=False)
        f1 = model.run_eigen()
        if S == 0: f0 = f1
        drop = (f0-f1)/f0*100 if f0>0 else 0
        err = (f1-FN_FIELD)/FN_FIELD*100
        print(f"  S={S:.1f}m: f_n={f1:.4f} Hz  drop={drop:.1f}%  err={err:+.1f}%", flush=True)
        results.append({'analysis':'eigenvalue','scour_m':S,'f_n_Hz':f1,'drop_pct':drop})
    return pd.DataFrame(results)


# =============================================================================
# ANALYSIS 2: PUSHOVER (H_collapse comparison with OptumGX)
# =============================================================================
def run_pushover(model, scour=0.0):
    print("\n" + "="*70, flush=True)
    print(f"ANALYSIS 2: PUSHOVER at S={scour:.1f}m", flush=True)
    print(f"  Tests: p_ult(z), y50(z) from OptumGX plates + dissipation", flush=True)
    print(f"  Validation target: Hmax_OptumGX = {HMAX_OPTUMGX:.0f} kN", flush=True)
    print("="*70, flush=True)

    model.build(scour, dashpot=False)
    hub = model.hub_node

    # Load pattern: unit horizontal force at hub
    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)
    ops.load(hub, 1000.0, 0.0, 0.0, 0.0, 0.0, 0.0)  # 1000 kN reference

    # Analysis settings
    ops.constraints('Transformation')
    ops.numberer('RCM')
    ops.system('BandGeneral')
    ops.test('NormDispIncr', 1.0e-4, 50)
    ops.algorithm('Newton')

    # Displacement-controlled push
    n_steps = 100
    du = 0.02  # 2cm per step, total 2m
    ops.integrator('DisplacementControl', hub, 1, du)
    ops.analysis('Static')

    curve = []
    for step in range(n_steps):
        ok = ops.analyze(1)
        if ok != 0:
            # Try smaller step
            ops.integrator('DisplacementControl', hub, 1, du/10)
            for _ in range(10):
                ok = ops.analyze(1)
                if ok != 0: break
            ops.integrator('DisplacementControl', hub, 1, du)
            if ok != 0:
                print(f"  Pushover failed at step {step}", flush=True)
                break

        u_hub = ops.nodeDisp(hub, 1)
        load_factor = ops.getTime()
        H_applied = load_factor * 1000.0  # kN

        curve.append({'u_hub_m': u_hub, 'H_kN': H_applied, 'step': step+1})

    df_curve = pd.DataFrame(curve)
    if len(df_curve) > 0:
        H_max_ops = df_curve['H_kN'].max()
        u_at_max = df_curve.loc[df_curve['H_kN'].idxmax(), 'u_hub_m']
        ratio = H_max_ops / HMAX_OPTUMGX * 100 if HMAX_OPTUMGX > 0 else 0

        print(f"  Hub displacement range: 0 to {df_curve['u_hub_m'].max():.3f} m", flush=True)
        print(f"  H_max (OpenSeesPy): {H_max_ops:.0f} kN at u={u_at_max:.3f} m", flush=True)
        print(f"  H_max (OptumGX LA): {HMAX_OPTUMGX:.0f} kN", flush=True)
        print(f"  Ratio: {ratio:.1f}%", flush=True)

        # Initial stiffness from first few points
        if len(df_curve) > 5:
            k_init = (df_curve['H_kN'].iloc[3] - df_curve['H_kN'].iloc[0]) / \
                     (df_curve['u_hub_m'].iloc[3] - df_curve['u_hub_m'].iloc[0])
            print(f"  Initial stiffness: {k_init:.0f} kN/m", flush=True)

    return df_curve


# =============================================================================
# ANALYSIS 3: TRANSIENT FREE VIBRATION (damping from dashpots)
# =============================================================================
def run_transient(model, scour=0.0):
    print("\n" + "="*70, flush=True)
    print(f"ANALYSIS 3: TRANSIENT FREE VIBRATION at S={scour:.1f}m", flush=True)
    print("  Tests: dashpot c(z) from Wolf-Gazetas + dissipation w(z)", flush=True)
    print("="*70, flush=True)

    model.build(scour, dashpot=True)
    hub = model.hub_node

    # Step 1: Apply static impulse (displacement, then release)
    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)
    ops.load(hub, 100.0, 0.0, 0.0, 0.0, 0.0, 0.0)  # small force

    ops.constraints('Transformation')
    ops.numberer('RCM')
    ops.system('BandGeneral')
    ops.test('NormDispIncr', 1.0e-6, 20)
    ops.algorithm('Newton')
    ops.integrator('LoadControl', 1.0)
    ops.analysis('Static')
    ops.analyze(1)

    u_init = ops.nodeDisp(hub, 1)
    print(f"  Initial displacement: {u_init*1000:.3f} mm", flush=True)

    # Step 2: Remove load and run free vibration
    ops.remove('loadPattern', 1)
    ops.wipeAnalysis()

    dt = 0.01  # 10ms timesteps
    t_total = 20.0  # 20 seconds of free vibration
    n_steps = int(t_total / dt)

    ops.constraints('Transformation')
    ops.numberer('RCM')
    ops.system('BandGeneral')
    ops.test('NormDispIncr', 1.0e-6, 20)
    ops.algorithm('Newton')
    ops.integrator('Newmark', 0.5, 0.25)
    ops.analysis('Transient')

    history = []
    for step in range(n_steps):
        ok = ops.analyze(1, dt)
        if ok != 0:
            print(f"  Transient failed at t={step*dt:.2f}s", flush=True)
            break
        t = ops.getTime()
        u = ops.nodeDisp(hub, 1)
        history.append({'t_s': t, 'u_hub_m': u})

    df_hist = pd.DataFrame(history)
    if len(df_hist) > 10:
        # Extract damping ratio from logarithmic decrement
        u_arr = df_hist['u_hub_m'].values
        t_arr = df_hist['t_s'].values

        # Find peaks
        peaks_idx = []
        for i in range(1, len(u_arr)-1):
            if u_arr[i] > u_arr[i-1] and u_arr[i] > u_arr[i+1] and u_arr[i] > 0:
                peaks_idx.append(i)

        if len(peaks_idx) >= 3:
            # Logarithmic decrement between first few peaks
            u_peaks = [u_arr[i] for i in peaks_idx[:5]]
            t_peaks = [t_arr[i] for i in peaks_idx[:5]]

            if len(u_peaks) >= 2 and u_peaks[0] > 0 and u_peaks[-1] > 0:
                n_cycles = len(u_peaks) - 1
                delta = math.log(u_peaks[0] / u_peaks[-1]) / n_cycles
                zeta = delta / (2 * math.pi)
                T_d = (t_peaks[-1] - t_peaks[0]) / n_cycles if n_cycles > 0 else 0
                f_d = 1/T_d if T_d > 0 else 0

                print(f"  Peaks found: {len(peaks_idx)}", flush=True)
                print(f"  Damped frequency: {f_d:.4f} Hz", flush=True)
                print(f"  Logarithmic decrement: {delta:.4f}", flush=True)
                print(f"  Damping ratio: {zeta:.4f} ({zeta*100:.1f}%)", flush=True)
                print(f"  Expected from Tier 2+3: ~5.1%", flush=True)
            else:
                print("  Could not compute damping (peaks too small)", flush=True)
        else:
            print(f"  Only {len(peaks_idx)} peaks found, need 3+", flush=True)

    return df_hist


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print("="*70, flush=True)
    print("OpenSeesPy v6: Three Analyses with Generalized Vesic Framework", flush=True)
    print("All spring parameters from OptumGX limit analysis", flush=True)
    print("="*70, flush=True)

    model = TripodModel()
    model.load_data()
    print(f"Hub node: {model.hub_node}", flush=True)

    # --- ANALYSIS 1: EIGENVALUE ---
    df_eigen = run_eigenvalue(model)
    df_eigen.to_csv(OUTPUT / 'v6_eigenvalue.csv', index=False)

    # --- ANALYSIS 2: PUSHOVER ---
    df_push = run_pushover(model, scour=0.0)
    df_push.to_csv(OUTPUT / 'v6_pushover_S0.csv', index=False)

    # Also at S=2m for comparison
    df_push2 = run_pushover(model, scour=2.0)
    df_push2.to_csv(OUTPUT / 'v6_pushover_S2.csv', index=False)

    # --- ANALYSIS 3: TRANSIENT ---
    df_trans = run_transient(model, scour=0.0)
    df_trans.to_csv(OUTPUT / 'v6_transient_S0.csv', index=False)

    # --- SUMMARY ---
    print("\n" + "="*70, flush=True)
    print("SUMMARY: THREE ANALYSES WITH OPTUMGX-DERIVED SPRINGS", flush=True)
    print("="*70, flush=True)
    print("Analysis 1 (Eigenvalue):", flush=True)
    print(f"  f_n at S=0: {df_eigen[df_eigen['scour_m']==0]['f_n_Hz'].values[0]:.4f} Hz "
          f"(field: {FN_FIELD})", flush=True)
    f4 = df_eigen[df_eigen['scour_m']==4.0]['f_n_Hz'].values[0]
    print(f"  f_n at S=4: {f4:.4f} Hz "
          f"(drop: {df_eigen[df_eigen['scour_m']==4.0]['drop_pct'].values[0]:.1f}%)", flush=True)

    if len(df_push) > 0:
        print("Analysis 2 (Pushover S=0):", flush=True)
        print(f"  H_max: {df_push['H_kN'].max():.0f} kN "
              f"(OptumGX: {HMAX_OPTUMGX:.0f} kN)", flush=True)

    print("Analysis 3 (Transient): see damping results above", flush=True)
    print("="*70, flush=True)

    # --- PLOT ---
    if HAS_MPL:
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))

        # Panel 1: f_n vs scour
        ax = axes[0]
        ax.plot(df_eigen['scour_m'], df_eigen['f_n_Hz'], 'b-o', lw=2, ms=6)
        ax.axhline(FN_FIELD, color='r', ls='--', lw=1.5, label=f'Field {FN_FIELD} Hz')
        ax.set_xlabel('Scour Depth (m)'); ax.set_ylabel('f_n (Hz)')
        ax.set_title('Analysis 1: Eigenvalue'); ax.legend(); ax.grid(True, alpha=0.3)

        # Panel 2: Pushover curve
        ax = axes[1]
        if len(df_push) > 0:
            ax.plot(df_push['u_hub_m']*1000, df_push['H_kN']/1000, 'b-', lw=2, label='S=0m')
        if len(df_push2) > 0:
            ax.plot(df_push2['u_hub_m']*1000, df_push2['H_kN']/1000, 'r--', lw=2, label='S=2m')
        ax.axhline(HMAX_OPTUMGX/1000, color='g', ls=':', lw=1.5, label=f'OptumGX {HMAX_OPTUMGX/1000:.0f} MN')
        ax.set_xlabel('Hub Displacement (mm)'); ax.set_ylabel('Lateral Load (MN)')
        ax.set_title('Analysis 2: Pushover'); ax.legend(); ax.grid(True, alpha=0.3)

        # Panel 3: Free vibration
        ax = axes[2]
        if len(df_trans) > 0:
            ax.plot(df_trans['t_s'], df_trans['u_hub_m']*1000, 'b-', lw=0.5)
        ax.set_xlabel('Time (s)'); ax.set_ylabel('Hub Displacement (mm)')
        ax.set_title('Analysis 3: Free Vibration'); ax.grid(True, alpha=0.3)

        fig.suptitle('Three Analyses: OptumGX-Derived BNWF Framework', fontsize=14)
        fig.tight_layout()
        fig.savefig(OUTPUT / 'v6_three_analyses.png', dpi=300)
        print(f"\nSaved: {OUTPUT / 'v6_three_analyses.png'}", flush=True)
        plt.close()

    print("DONE", flush=True)
