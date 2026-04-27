"""
Server configuration for the WebRTC + WebSocket backend.
All runtime-configurable values live here; Python code never hard-codes them.
"""
import os
import socket


def _detect_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Detect or override via env
HOST_IP = os.getenv("PHYS_HOST_IP", _detect_lan_ip())

# HTTP server (WebRTC signaling + camera control)
HTTP_HOST = "0.0.0.0"
HTTP_PORT = int(os.getenv("PHYS_HTTP_PORT", "8080"))

# WebSocket server (simulation control + telemetry)
WS_HOST = "0.0.0.0"
WS_PORT = int(os.getenv("PHYS_WS_PORT", "30000"))

# Video capture
VIDEO_WIDTH = int(os.getenv("PHYS_VIDEO_W", "2560"))
VIDEO_HEIGHT = int(os.getenv("PHYS_VIDEO_H", "1440"))
VIDEO_FPS = 30

# Telemetry
TELEMETRY_BROADCAST_INTERVAL = 0.01  # 100 Hz
SIMULATION_CHECK_INTERVAL = 0.1

# USD scene
DEFAULT_USD_PATH = os.getenv(
    "PHYS_USD_PATH",
    os.path.join(PROJECT_ROOT, "Experiment", "exp.usd"),
)

# Experiment 1 — angular momentum
EXP1_DISK_PATH = "/World/exp1/disk"
EXP1_RING_PATH = "/World/exp1/ring"
EXP1_DEFAULT_DISK_MASS = 1.0
EXP1_DEFAULT_RING_MASS = 1.0
EXP1_DEFAULT_INITIAL_VELOCITY = 0.0

# Experiment 2 — large-amplitude pendulum (procedural RK4 visual pendulum)
EXP2_PHYSICS_DT = 1.0 / 240.0
EXP2_RENDER_EVERY_N = 6
EXP2_ROD_LENGTH = 0.35           # m
EXP2_ROD_MASS = 0.028            # kg
EXP2_DEFAULT_BOB_MASS1 = 0.075   # kg (lower bob, red)
EXP2_DEFAULT_BOB_MASS2 = 0.075   # kg (upper bob, blue)
EXP2_DEFAULT_R1 = 0.175          # m (pivot → bob1 distance)
EXP2_DEFAULT_R2 = 0.145          # m (pivot → bob2 distance)
EXP2_DEFAULT_DAMPING = 0.0025    # angular damping coefficient
EXP2_DEFAULT_AMPLITUDE = 0.35    # rad (initial amplitude)
EXP2_PIVOT_POS = (0.0, 0.0, 0.80)
EXP2_ROD_DRAW_WIDTH = 0.018
EXP2_ROD_DRAW_DEPTH = 0.018
EXP2_BOB_DRAW_SIZE = 0.048
EXP2_PIVOT_DRAW_SIZE = 0.05
EXP2_FLOOR_Z = -0.24

# Experiment 5 — physical pendulum (rotational inertia)
# A uniform bar is pivoted at distance x from its centre of mass and swings
# under gravity around a Y-axis revolute joint (vertical XZ plane).
# T(x) = 2π √((L²/12 + x²) / (g · x))   →   T_min at  x = L / √12
EXP5_PIVOT_PATH = "/World/exp5/pivot"
EXP5_BAR_PATH = "/World/exp5/bar"
EXP5_MATERIAL_PATH = "/World/exp5/PhysicsMaterial"
EXP5_JOINT_PATH = "/World/exp5/RevoluteJoint"
EXP5_DEFAULT_M = 0.28                 # kg   bar mass
EXP5_DEFAULT_L = 0.28                 # m    bar length
EXP5_DEFAULT_X = 0.10                 # m    pivot → CM distance
EXP5_DEFAULT_THETA0_DEG = 5.0         # deg  initial angular displacement
EXP5_BAR_THICKNESS = 0.02             # m    bar cross-section (square)
EXP5_PIVOT_HEIGHT = 0.70              # m    pivot z-position above floor
EXP5_GROUND_Z = -0.24                 # m    floor elevation
EXP5_SOLVER_POS_ITERS = 64
EXP5_SOLVER_VEL_ITERS = 32

# Experiment 4 — driven damped torsional oscillator (PhysX-native)
#
# An aluminium disk is held by a torsional spring (two springs coupling the
# disk to a fixed post + a motor-driven arm) and damped by an adjustable
# magnetic brake. PhysX implementation:
#     • Kinematic pivot cube
#     • Dynamic disk (flat cuboid) with explicit disk inertia I = ½MR²
#     • Revolute joint around +Z, with angular DriveAPI (type=force)
#         stiffness  = κ   (spring restoring torque)
#         damping    = b   (magnetic damping)
#         target_pos = A_drive·sin(ω_d·t)   (sinusoidal driver via the
#                      spring coupling → produces τ₀·sin(ωt) with τ₀ = κ·A)
#     • A visual "driver arm" rotates synchronously with target_pos.
#
# Equation of motion (PhysX integrates this to full precision):
#     I·θ̈ + b·θ̇ + κ·θ = κ·A_drive·sin(ω_d·t)
# with:
#     ω₀ = √(κ/I)             natural angular frequency
#     γ  = b/I                 damping rate
#     Q  = ω₀/(2γ) = √(κI)/b   quality factor
EXP4_PIVOT_PATH = "/World/exp4/pivot"
EXP4_DISK_PATH = "/World/exp4/disk"
EXP4_DRIVER_ARM_PATH = "/World/exp4/driver_arm"
EXP4_MATERIAL_PATH = "/World/exp4/PhysicsMaterial"
EXP4_JOINT_PATH = "/World/exp4/RevoluteJoint"

EXP4_DEFAULT_SPRING_K = 0.006         # N·m/rad  (torsional spring const)
EXP4_DEFAULT_DAMPING_GAMMA = 0.5      # 1/s      (b/I ratio — PDF-style)
EXP4_DEFAULT_DRIVE_AMP = 0.30         # rad      (driver arm amplitude)
EXP4_DEFAULT_DRIVE_FREQ = 1.0         # Hz       (driver frequency)
EXP4_DISK_MASS = 0.120                # kg       (aluminium disk)
EXP4_DISK_RADIUS = 0.0475             # m        (PASCO ME-8750 disk)
EXP4_DISK_THICKNESS = 0.006           # m        (plate thickness)
EXP4_PIVOT_HEIGHT = 0.50              # m        (above floor)
EXP4_GROUND_Z = -0.24                 # m
EXP4_SOLVER_POS_ITERS = 96
EXP4_SOLVER_VEL_ITERS = 48
EXP4_DRIVER_UPDATE_HZ = 120.0         # target_position refresh rate

# Experiment 3 — ballistic pendulum (projectile fired into swinging catcher)
# Physics:
#   Inelastic collision:   m_ball · v0 = (m_ball + m_pend) · v
#   Energy conservation:   ½ M v²     = M g L (1 − cos θmax)
#   ⇒   v0 = (m_ball + m_pend) / m_ball · √(2 g L (1 − cos θmax))
#
# Scene (all procedural, PhysX-driven):
#   • Kinematic pivot cube at (0, 0, PIVOT_HEIGHT).
#   • Pendulum rigid body with compound colliders:
#       - thin rod from pivot to catcher centre,
#       - 4-walled "cup" (back/left/right/floor) facing the launcher to trap
#         the ball on impact (classical styrofoam catcher analogue).
#   • Revolute joint (Y-axis) pivot ↔ pendulum → swings in the XZ plane.
#   • Ball: small DynamicCuboid fired with linear velocity v0 toward +X.
#   • Launcher: visual-only decoration on the −X side.
EXP3_PIVOT_PATH = "/World/exp3/pivot"
EXP3_PENDULUM_PATH = "/World/exp3/pendulum"
EXP3_BALL_PATH = "/World/exp3/ball"
EXP3_LAUNCHER_PATH = "/World/exp3/launcher"
EXP3_MATERIAL_BALL_PATH = "/World/exp3/BallMaterial"
EXP3_MATERIAL_CATCHER_PATH = "/World/exp3/CatcherMaterial"
EXP3_JOINT_PATH = "/World/exp3/RevoluteJoint"

EXP3_DEFAULT_BALL_MASS = 0.0165     # kg  (PASCO ME-6825A ≈ 16.5 g steel ball)
EXP3_DEFAULT_PEND_MASS = 0.1536     # kg  (PASCO ME-6829 ≈ 153.6 g catcher)
EXP3_DEFAULT_V0 = 5.0               # m/s (muzzle velocity, cock position 3)
EXP3_DEFAULT_L = 0.30               # m   pivot-to-CM distance

EXP3_PIVOT_HEIGHT = 0.80            # m   pivot above floor (world-Z)
EXP3_GROUND_Z = -0.24               # m
EXP3_BALL_SIZE = 0.025              # m   cube side (~2.5 cm, approximates Ø25 mm ball)
EXP3_ROD_THICKNESS = 0.010          # m   rod cross-section (square)
EXP3_CATCHER_W = 0.08               # m   catcher outer width/depth (X,Y)
EXP3_CATCHER_H = 0.08               # m   catcher outer height (Z)
EXP3_CATCHER_WALL_T = 0.010         # m   wall thickness
EXP3_LAUNCHER_GAP = 0.04            # m   gap between launcher muzzle and catcher
EXP3_BALL_SPAWN_OFFSET = 0.015      # m   ball spawn offset in −X from catcher front
EXP3_SOLVER_POS_ITERS = 96
EXP3_SOLVER_VEL_ITERS = 48
EXP3_WARMUP_SECONDS = 0.05          # short settle before firing
EXP3_AUTO_SETTLE_SECONDS = 6.0      # safety timeout for "settled" phase

# Experiment 6 — centripetal force (PhysX-native rotating spring)
#
# Physical apparatus (PASCO ME-8952 style): a mass is attached to a rotating
# horizontal arm by a spring. As the rotor spins at angular velocity ω the
# mass tries to fly outward; the spring stretches until the spring force
# balances the centripetal force required to keep the mass in circular
# motion.  The stretched spring's force *is* the measured centripetal
# force (F_c = k · Δx).
#
# PhysX implementation — the motion is integrated, NOT derived from F=mv²/r:
#   • Kinematic "rotor" Xform at origin that is spun about +Z at a user-set
#     angular velocity by an async pose-driver task (same pattern as the
#     exp4 driver arm).
#   • Dynamic "bob" rigid body positioned at the target radius along the
#     rotor's local +X axis.
#   • Prismatic joint between rotor (body0) and bob (body1) along the
#     rotor's local X axis, with a UsdPhysics.DriveAPI "linear" configured
#     with stiffness = k_spring, damping = c, target_position = r_target.
#   • PhysX integrates the bob's horizontal motion.  As the rotor spins the
#     kinematic pose changes each tick → PhysX sees the constraint move →
#     the bob is accelerated tangentially → centrifugal tendency stretches
#     the spring → steady-state r_actual ≈ k r_target / (k − m ω²).
#   • A frictionless horizontal table supports the bob against gravity
#     (gravity remains ON, per project rule).  Bob translation along Z and
#     rotation about X/Y are locked for numerical stability.
#
# Measured telemetry (all derived from PhysX state, never from the formula):
#   r_actual  = √(x²+y²) of bob
#   v_tan    = horizontal |v| of bob
#   F_meas   = k · (r_actual − r_target)        (the real spring force)
#   F_check  = m · v_tan² / r_actual            (force the bob experiences)
#   F_theory = m · ω² · r_target                (analytic reference)
EXP6_ROOT_PATH = "/World/exp6"
EXP6_ANCHOR_PATH = "/World/exp6/world_anchor"
EXP6_ROTOR_PATH = "/World/exp6/rotor"              # kinematic rigid body (body0 of joint)
EXP6_VISUAL_FRAME_PATH = "/World/exp6/visual_frame"  # plain Xform that rotates in sync
EXP6_BOB_PATH = "/World/exp6/bob"
EXP6_TABLE_PATH = "/World/exp6/table"
EXP6_SHAFT_VISUAL_PATH = "/World/exp6/visual_frame/shaft"
EXP6_ARM_VISUAL_PATH = "/World/exp6/visual_frame/arm"
EXP6_COUNTER_VISUAL_PATH = "/World/exp6/visual_frame/counter_mass"
EXP6_SPRING_VISUAL_PATH = "/World/exp6/visual_frame/spring"
EXP6_HUB_VISUAL_PATH = "/World/exp6/visual_frame/hub"
EXP6_PRISM_JOINT_PATH = "/World/exp6/PrismaticJoint"
EXP6_TABLE_MATERIAL_PATH = "/World/exp6/TableMaterial"
EXP6_BOB_MATERIAL_PATH = "/World/exp6/BobMaterial"

EXP6_DEFAULT_MASS = 0.030            # kg   (30 g, matches classmate default)
EXP6_DEFAULT_RADIUS = 0.15           # m    (target spring rest length)
EXP6_DEFAULT_OMEGA = 5.0             # rad/s  (initial rotor speed)
EXP6_DEFAULT_SPRING_K = 250.0        # N/m  (stiff spring so r_actual ≈ r_target)
EXP6_DEFAULT_DAMPER = 0.4            # N·s/m
EXP6_DEFAULT_RAMP_TIME = 1.2         # s    (linear ramp from 0 to target ω)

EXP6_TABLE_Z = 0.70                  # m    (table top — bob rides on this)
EXP6_GROUND_Z = -0.24                # m
EXP6_TABLE_RADIUS = 0.55             # m    (>> max bob radius)
EXP6_TABLE_THICKNESS = 0.02          # m
EXP6_BOB_SIZE = 0.035                # m    cube side (≈ 3.5 cm)
EXP6_ARM_THICKNESS = 0.015           # m    arm cross-section
EXP6_SHAFT_RADIUS = 0.020            # m    visual shaft half-width
EXP6_PIVOT_HEIGHT = 0.18             # m    shaft height above table top
EXP6_PRISM_LIMIT_MIN = -0.10         # m    inward slack
EXP6_PRISM_LIMIT_MAX = 0.60          # m    outward limit (safety)

EXP6_ROTOR_UPDATE_HZ = 240.0         # Hz   rotor pose-driver update rate
EXP6_SOLVER_POS_ITERS = 128
EXP6_SOLVER_VEL_ITERS = 64
EXP6_WARMUP_SECONDS = 0.15

# Experiment 7 — momentum conservation (two-cart collision)
EXP7_CART1_PATH = "/World/exp7/cart1"
EXP7_CART2_PATH = "/World/exp7/cart2"
EXP7_GROUND_PATH = "/World/exp7/ground"
EXP7_MATERIAL_PATH = "/World/exp7/PhysicsMaterial"
EXP7_DEFAULT_MASS1 = 0.25   # kg
EXP7_DEFAULT_MASS2 = 0.25   # kg
EXP7_DEFAULT_V1 = 0.40      # m/s (rightward)
EXP7_DEFAULT_V2 = -0.40     # m/s (leftward — head-on)
EXP7_DEFAULT_RESTITUTION = 1.0
EXP7_CART_SIZE = (0.12, 0.08, 0.06)     # metres (l × w × h)
EXP7_CART1_INIT_POS = (-0.50, 0.0, 0.03)
EXP7_CART2_INIT_POS = (0.50, 0.0, 0.03)
EXP7_WARMUP_SECONDS = 0.15
EXP7_SOLVER_POS_ITERS = 64
EXP7_SOLVER_VEL_ITERS = 32

# Experiment 8 — resonance in air column (driven 1-D wave equation)
# A 1-D scalar wave equation is integrated by a finite-difference leapfrog
# scheme in the telemetry loop; the result drives the visible position of N
# kinematic "air-slice" rigid bodies arranged along the tube in Isaac Sim.
# Physics:
#     ∂²u/∂t² = c² ∂²u/∂x² − 2 γ ∂u/∂t
#     Speaker end  (x = 0):  u(0, t) = A sin(2π f t)      (Dirichlet)
#     Closed end   (x = L):  u(L, t) = 0                   (Dirichlet)
#     Open end     (x = L):  ∂u/∂x|_L = 0                  (Neumann)
# Resonance (closed tube):  L + 0.3 d = (2n − 1) λ/4,  n = 1, 2, 3, …
# Resonance (open tube):    L + 0.6 d = n λ/2,         n = 1, 2, 3, …
#
# To keep the solver stable at the native PhysX 240 Hz rate we scale the sound
# speed down (c_sim ≪ 340 m/s) and apply the same scale factor to the driver
# frequency. The dimensionless ratio f·L/c is preserved, so every resonance
# pattern faithfully reproduces the real lab.
EXP8_ROOT_PATH = "/World/exp8"
EXP8_TUBE_PATH = "/World/exp8/tube"
EXP8_SPEAKER_PATH = "/World/exp8/speaker"
EXP8_DIAPHRAGM_PATH = "/World/exp8/diaphragm"
EXP8_PISTON_PATH = "/World/exp8/piston"
EXP8_SLICE_ROOT = "/World/exp8/slices"
EXP8_SLICE_PATH_TEMPLATE = "/World/exp8/slices/slice_{:02d}"
EXP8_MARKER_ROOT = "/World/exp8/markers"
EXP8_MARKER_PATH_TEMPLATE = "/World/exp8/markers/marker_{:02d}"

EXP8_N_SLICES = 48                       # spatial grid nodes (interior)
EXP8_TUBE_TOTAL_LENGTH = 1.20            # m   physical tube length (PASCO 120 cm)
EXP8_TUBE_DIAMETER = 0.040               # m   inner diameter d (≈ 4 cm)
EXP8_TUBE_WALL = 0.0025                  # m   wall thickness (visual)
EXP8_TUBE_BASE_X = 0.0                   # m   speaker-end x-position
EXP8_TUBE_Y = 0.0                        # m   tube centre-line Y
EXP8_TUBE_Z = 0.40                       # m   tube centre-line above floor
EXP8_GROUND_Z = -0.02                    # m   stand + ground clearance
EXP8_SLICE_DRAW_RADIUS = 0.014           # m   visual sphere radius
EXP8_AMP_SCALE = 6.0                     # dimensionless visual magnification

EXP8_C_SIM = 20.0                        # m/s  simulated speed of sound
EXP8_C_REAL = 340.0                      # m/s  real speed of sound (reference)
EXP8_FREQ_SCALE = EXP8_C_SIM / EXP8_C_REAL
EXP8_DEFAULT_LENGTH_CM = 50.0
EXP8_DEFAULT_FREQUENCY = 170.0           # Hz  real-world frequency (≈ f₁ of 50 cm closed tube)
EXP8_DEFAULT_AMPLITUDE_MM = 1.5          # mm  speaker diaphragm excursion
EXP8_DEFAULT_DAMPING = 0.8               # 1/s wave-equation damping γ
EXP8_DEFAULT_MODE = "closed"             # "closed" or "open"
EXP8_PHYS_SUBSTEPS = 12                  # FDM sub-steps per wave-loop tick
EXP8_WAVE_TICK_HZ = 120.0                # Hz  wave-solver update rate
EXP8_TELEMETRY_HISTORY = 256             # samples kept for probe trace
EXP8_RESONANCE_THRESHOLD = 3.0           # amp ratio (RMS / drive) ⇒ "resonant"

# Replicator
REPLICATOR_INIT_MAX_RETRIES = 3
REPLICATOR_INIT_RETRY_DELAY = 1.0
FRAME_CAPTURE_TIMEOUT = 0.2

# VR — Meta Quest hand tracking
VR_ENABLED = os.getenv("PHYS_VR_ENABLED", "true").lower() in ("1", "true", "yes")
VR_UDP_HOST = "0.0.0.0"
VR_UDP_PORT = int(os.getenv("PHYS_VR_PORT", "8888"))
VR_UDP_TIMEOUT = 0.1
VR_UPDATE_RATE = 60.0                  # expected Quest send rate (Hz)
VR_SMOOTHING = True
VR_SMOOTHING_ALPHA = 0.3
VR_POSITION_SCALE = 2.0               # mapping from Quest workspace to scene
VR_POSITION_OFFSET = (0.5, 0.0, 0.5)  # scene-space offset after scaling
VR_PINCH_THRESHOLD = 0.6              # pinch strength to trigger grasp
VR_GRASP_DISTANCE = 0.15              # metres — hand-to-object grab range
VR_RELEASE_DELAY = 0.1                # seconds — debounce before release
VR_HAND_SIZE = (0.08, 0.04, 0.12)     # visual cuboid size (metres)
VR_LEFT_HAND_PATH = "/World/vr/left_hand"
VR_RIGHT_HAND_PATH = "/World/vr/right_hand"
