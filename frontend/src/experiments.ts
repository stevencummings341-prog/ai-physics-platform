import { type ExperimentConfig } from './types';

export const EXPERIMENTS: ExperimentConfig[] = [
  {
    id: 'exp-01-angular-momentum',
    title: 'Conservation of Angular Momentum',
    description: 'Verify angular momentum conservation by dropping a ring or disk onto a spinning turntable and measuring the angular velocity change.',
    thumbnail: 'https://picsum.photos/seed/angular-momentum/400/225',
    usdPath: 'Experiment/exp.usd',
    experimentNumber: '1',
    difficulty: 'Easy',
    isLocked: false,
    controls: [
      { id: 'initial_velocity', label: 'Initial ω (rad/s)', type: 'slider', min: 15, max: 30, step: 0.5, defaultValue: 20, command: 'set_initial_velocity' },
    ],
    chartConfig: [
      { key: 'disk_angular_velocity', color: '#3b82f6', label: 'Lower Disk ω (rad/s)', yAxisId: 'left' },
      { key: 'ring_angular_velocity', color: '#10b981', label: 'Object ω (rad/s)', yAxisId: 'left' },
      { key: 'angular_momentum', color: '#f59e0b', label: 'L (kg·m²/s)', yAxisId: 'right' }
    ],
    extraMetrics: [
      { key: 'kinetic_energy', label: 'KE (J)', color: '#ef4444' }
    ]
  },
  {
    id: 'exp-02-large-pendulum',
    title: 'Large Amplitude Pendulum',
    description: 'Investigate pendulum motion at large angles beyond the small-angle approximation. Uses RK4 integration for a physical compound pendulum with two bobs. Compare measured period with series-expansion theory.',
    thumbnail: 'https://picsum.photos/seed/pendulum/400/225',
    usdPath: 'Experiment/exp.usd',
    experimentNumber: '2',
    difficulty: 'Easy',
    isLocked: false,
    controls: [
      { id: 'amplitude', label: 'Initial Amplitude (rad)', type: 'slider', min: 0.10, max: 2.80, step: 0.05, defaultValue: 0.35, command: 'set_exp2_amplitude' },
      { id: 'damping', label: 'Damping Coefficient', type: 'slider', min: 0.0, max: 0.02, step: 0.0005, defaultValue: 0.0025, command: 'set_exp2_damping' },
      { id: 'run', label: 'Run Pendulum', type: 'button', command: 'start_simulation' },
      { id: 'reset', label: 'Reset', type: 'button', command: 'reset' },
      { id: 'full_experiment', label: 'Generate Full Report', type: 'button', command: 'run_exp2_full_experiment' }
    ],
    chartConfig: [
      { key: 'theta', color: '#8b5cf6', label: 'θ (°)', yAxisId: 'left' },
      { key: 'omega', color: '#3b82f6', label: 'ω (rad/s)', yAxisId: 'right' },
    ],
    extraMetrics: [
      { key: 'period', label: 'Measured T (s)', color: '#10b981' },
      { key: 'T0_theory', label: 'T₀ theory (s)', color: '#f59e0b' },
      { key: 'T_series', label: 'T series (s)', color: '#ef4444' }
    ]
  },
  {
    id: 'exp-03-ballistic-pendulum',
    title: 'Ballistic Pendulum (Conservation of Momentum + Energy)',
    description: 'A projectile of mass m_ball fired at v₀ is caught inelastically by a pendulum of mass m_pend. PhysX handles the compound rigid body, revolute joint, and contact physics. The measured maximum swing angle θₘₐₓ gives v₀ = (m_ball+m_pend)/m_ball · √(2gL(1−cos θₘₐₓ)).',
    thumbnail: 'https://picsum.photos/seed/ballistic/400/225',
    usdPath: 'Experiment/exp.usd',
    experimentNumber: '3',
    difficulty: 'Medium',
    isLocked: false,
    controls: [
      { id: 'ball_mass', label: 'Ball Mass m (kg)', type: 'slider', min: 0.005, max: 0.100, step: 0.001, defaultValue: 0.0165, command: 'set_ball_mass' },
      { id: 'pend_mass', label: 'Pendulum Mass M (kg)', type: 'slider', min: 0.050, max: 0.500, step: 0.005, defaultValue: 0.1536, command: 'set_pend_mass' },
      { id: 'exp3_v0', label: 'Launch Velocity v₀ (m/s)', type: 'slider', min: 1.0, max: 8.0, step: 0.1, defaultValue: 5.0, command: 'set_exp3_v0' },
      { id: 'exp3_L', label: 'Rod Length L (m)', type: 'slider', min: 0.15, max: 0.50, step: 0.01, defaultValue: 0.30, command: 'set_exp3_L' },
      { id: 'run', label: 'Fire', type: 'button', command: 'start_simulation' },
      { id: 'reset', label: 'Reset', type: 'button', command: 'reset' }
    ],
    chartConfig: [
      { key: 'theta', color: '#a855f7', label: 'θ (°)', yAxisId: 'left' },
      { key: 'omega', color: '#3b82f6', label: 'ω (rad/s)', yAxisId: 'right' },
      { key: 'ball_velocity', color: '#f59e0b', label: 'Ball |v| (m/s)', yAxisId: 'left' },
      { key: 'height', color: '#10b981', label: 'h (m)', yAxisId: 'right' }
    ],
    extraMetrics: [
      { key: 'theta_max', label: 'θ max (°)', color: '#f97316' },
      { key: 'h_max', label: 'h max (m)', color: '#84cc16' },
      { key: 'v0_measured', label: 'v₀ measured (m/s)', color: '#22d3ee' },
      { key: 'v0_input', label: 'v₀ set (m/s)', color: '#cbd5f5' },
      { key: 'v0_error_pct', label: 'v₀ error (%)', color: '#f43f5e' },
      { key: 'v_after_ideal', label: 'v after (m/s)', color: '#facc15' },
      { key: 'ke_input', label: 'KE in (J)', color: '#a78bfa' },
      { key: 'ke_after_ideal', label: 'KE after (J)', color: '#60a5fa' },
      { key: 'ke_loss_percent', label: 'KE loss (%)', color: '#ef4444' }
    ]
  },
  {
    id: 'exp-04-driven-damped-oscillation',
    title: 'Driven Damped Harmonic Oscillations',
    description: 'An aluminium disk is held by a torsional spring (stiffness κ) and a magnetic damper (b), driven sinusoidally at frequency f. PhysX integrates I·θ̈ + b·θ̇ + κ·θ = κ·A·sin(2πf·t) in real time — sweep f to map the resonance curve and observe the phase lag approach 90° at ω = ω₀.',
    thumbnail: 'https://picsum.photos/seed/oscillation/400/225',
    usdPath: 'Experiment/exp.usd',
    experimentNumber: '4',
    difficulty: 'Medium',
    isLocked: false,
    controls: [
      { id: 'drive_frequency', label: 'Drive Frequency f (Hz)', type: 'slider', min: 0.20, max: 3.00, step: 0.02, defaultValue: 1.00, command: 'set_exp4_frequency' },
      { id: 'damping', label: 'Damping γ = b/I (1/s)', type: 'slider', min: 0.0, max: 3.0, step: 0.05, defaultValue: 0.5, command: 'set_exp4_damping' },
      { id: 'drive_amplitude', label: 'Driver Amplitude A (rad)', type: 'slider', min: 0.05, max: 1.00, step: 0.05, defaultValue: 0.30, command: 'set_exp4_drive_amplitude' },
      { id: 'spring', label: 'Torsional κ (N·m/rad)', type: 'slider', min: 0.002, max: 0.020, step: 0.001, defaultValue: 0.006, command: 'set_exp4_spring' },
      { id: 'run', label: 'Start Driver', type: 'button', command: 'start_simulation' },
      { id: 'free', label: 'Free Oscillation (measure ω₀)', type: 'button', command: 'exp4_free_oscillation' },
      { id: 'reset', label: 'Reset', type: 'button', command: 'reset' }
    ],
    chartConfig: [
      { key: 'theta', color: '#ef4444', label: 'Disk θ (°)', yAxisId: 'left' },
      { key: 'theta_drive', color: '#3b82f6', label: 'Driver θ_d (°)', yAxisId: 'left' },
      { key: 'omega', color: '#f59e0b', label: 'Disk ω (rad/s)', yAxisId: 'right' }
    ],
    extraMetrics: [
      { key: 'amplitude', label: 'Peak |θ| (°)', color: '#10b981' },
      { key: 'theory_amp_deg', label: 'Theory |θ₀| (°)', color: '#a855f7' },
      { key: 'f_natural', label: 'f₀ natural (Hz)', color: '#f59e0b' },
      { key: 'f_drive', label: 'f drive (Hz)', color: '#3b82f6' },
      { key: 'phase_lag_deg', label: 'Phase lag φ (°)', color: '#ec4899' },
      { key: 'quality_factor', label: 'Q = √(κI)/b', color: '#00f3ff' }
    ]
  },
  {
    id: 'exp-05-rotational-inertia',
    title: 'Rotational Inertia (Physical Pendulum)',
    description: 'A uniform bar is pivoted at distance x from its center of mass and oscillates under gravity. Measure the period T(x) = 2π√((L²/12 + x²)/(g·x)) and verify it reaches a minimum at x = L/√12.',
    thumbnail: 'https://picsum.photos/seed/inertia/400/225',
    usdPath: 'Experiment/exp.usd',
    experimentNumber: '5',
    difficulty: 'Medium',
    isLocked: false,
    controls: [
      { id: 'exp5_m', label: 'Bar Mass m (kg)', type: 'slider', min: 0.05, max: 1.0, step: 0.01, defaultValue: 0.28, command: 'set_exp5_m' },
      { id: 'exp5_L', label: 'Bar Length L (m)', type: 'slider', min: 0.10, max: 1.0, step: 0.01, defaultValue: 0.28, command: 'set_exp5_L' },
      { id: 'exp5_x', label: 'Pivot Distance x (m)', type: 'slider', min: 0.01, max: 0.50, step: 0.01, defaultValue: 0.10, command: 'set_exp5_x' },
      { id: 'exp5_theta0', label: 'Initial Angle θ₀ (°)', type: 'slider', min: 1, max: 15, step: 0.5, defaultValue: 5, command: 'set_exp5_theta0' },
      { id: 'run', label: 'Run Pendulum', type: 'button', command: 'start_simulation' },
      { id: 'reset', label: 'Reset', type: 'button', command: 'reset' }
    ],
    chartConfig: [
      { key: 'theta', color: '#a855f7', label: 'θ (°)', yAxisId: 'left' },
      { key: 'omega', color: '#3b82f6', label: 'ω (rad/s)', yAxisId: 'right' }
    ],
    extraMetrics: [
      { key: 'period', label: 'Measured T (s)', color: '#10b981' },
      { key: 'T_theory', label: 'T theory (s)', color: '#f59e0b' },
      { key: 'inertia', label: 'I about pivot (kg·m²)', color: '#ef4444' },
      { key: 'x_min_period', label: 'x min-period (m)', color: '#00f3ff' }
    ]
  },
  {
    id: 'exp-06-centripetal-force',
    title: 'Centripetal Force',
    description: 'Investigate the relationship between centripetal force, mass, and circular motion. (Coming Soon)',
    thumbnail: 'https://picsum.photos/seed/centripetal/400/225',
    usdPath: 'Experiment/exp.usd',
    experimentNumber: '6',
    difficulty: 'Easy',
    isLocked: true,
    controls: [
      { id: 'mass', label: 'Mass (kg)', type: 'slider', min: 0.1, max: 2, step: 0.1, defaultValue: 0.5, command: 'set_mass' },
      { id: 'radius', label: 'Radius (m)', type: 'slider', min: 0.1, max: 1, step: 0.05, defaultValue: 0.3, command: 'set_radius' },
      { id: 'angular_velocity', label: 'Angular Velocity (rad/s)', type: 'slider', min: 1, max: 10, step: 0.5, defaultValue: 5, command: 'set_angular_velocity' },
      { id: 'run', label: 'Run', type: 'button', command: 'start_simulation' },
      { id: 'reset', label: 'Reset', type: 'button', command: 'reset' }
    ],
    chartConfig: [
      { key: 'centripetal_force', color: '#fb923c', label: 'Centripetal Force (N)', yAxisId: 'left' },
      { key: 'tension', color: '#ff4444', label: 'String Tension (N)', yAxisId: 'right' }
    ]
  },
  {
    id: 'exp-07-momentum-conservation',
    title: 'Conservation of Momentum',
    description: 'Verify momentum conservation in elastic and inelastic collisions between two carts. Run 4 trials with adjustable mass, velocity, and restitution to generate a lab report.',
    thumbnail: 'https://picsum.photos/seed/momentum/400/225',
    usdPath: 'Experiment/exp.usd',
    experimentNumber: '7',
    difficulty: 'Easy',
    isLocked: false,
    controls: [
      { id: 'mass1', label: 'Cart 1 Mass (kg)', type: 'slider', min: 0.10, max: 2.0, step: 0.05, defaultValue: 0.25, command: 'set_mass1' },
      { id: 'mass2', label: 'Cart 2 Mass (kg)', type: 'slider', min: 0.10, max: 2.0, step: 0.05, defaultValue: 0.25, command: 'set_mass2' },
      { id: 'velocity1', label: 'Cart 1 Velocity (m/s)', type: 'slider', min: -2.0, max: 2.0, step: 0.05, defaultValue: 0.40, command: 'set_velocity1' },
      { id: 'velocity2', label: 'Cart 2 Velocity (m/s)', type: 'slider', min: -2.0, max: 2.0, step: 0.05, defaultValue: -0.40, command: 'set_velocity2' },
      { id: 'elasticity', label: 'Restitution (0=inelastic, 1=elastic)', type: 'slider', min: 0, max: 1, step: 0.05, defaultValue: 1.0, command: 'set_elasticity' },
      { id: 'run', label: 'Run Collision', type: 'button', command: 'start_simulation' },
      { id: 'reset', label: 'Reset', type: 'button', command: 'reset' }
    ],
    chartConfig: [
      { key: 'v1', color: '#ef4444', label: 'Cart 1 v (m/s)', yAxisId: 'left' },
      { key: 'v2', color: '#3b82f6', label: 'Cart 2 v (m/s)', yAxisId: 'left' },
      { key: 'p_total', color: '#10b981', label: 'Total p (kg·m/s)', yAxisId: 'right' },
    ],
    extraMetrics: [
      { key: 'ke_total', label: 'Total KE (J)', color: '#f59e0b' }
    ]
  },
  {
    id: 'exp-08-resonance-air-column',
    title: 'Resonance in Air Column',
    description: 'Drive a 120 cm PASCO resonance tube with a signal-generator speaker and locate standing-wave resonances by adjusting the piston (tube length) or the driver frequency. The server solves the driven 1-D wave equation inside Isaac Sim (via PhysX-visualised air slices) so resonance emerges from authentic transient dynamics — not from a closed-form formula.',
    thumbnail: 'https://picsum.photos/seed/resonance/400/225',
    usdPath: 'Experiment/exp.usd',
    experimentNumber: '8',
    difficulty: 'Medium',
    isLocked: false,
    controls: [
      { id: 'length', label: 'Column Length L (cm)', type: 'slider', min: 10, max: 120, step: 0.5, defaultValue: 50, command: 'set_length' },
      { id: 'frequency', label: 'Frequency f (Hz)', type: 'slider', min: 50, max: 1200, step: 1, defaultValue: 170, command: 'set_frequency' },
      { id: 'amplitude', label: 'Speaker Amplitude (mm)', type: 'slider', min: 0.1, max: 5.0, step: 0.1, defaultValue: 1.5, command: 'set_exp8_amplitude' },
      { id: 'damping', label: 'Air Damping γ (1/s)', type: 'slider', min: 0.0, max: 6.0, step: 0.1, defaultValue: 0.8, command: 'set_exp8_damping' },
      { id: 'tube_closed', label: 'Closed Tube (piston in)', type: 'button', command: 'exp8_closed_tube' },
      { id: 'tube_open', label: 'Open Tube (piston out)', type: 'button', command: 'exp8_open_tube' },
      { id: 'run', label: 'Generate Tone', type: 'button', command: 'start_simulation' },
      { id: 'stop', label: 'Stop', type: 'button', command: 'stop_simulation' },
      { id: 'reset', label: 'Reset', type: 'button', command: 'reset' }
    ],
    chartConfig: [
      { key: 'probe_value', color: '#ec4899', label: 'Probe Displacement (m)', yAxisId: 'left' },
      { key: 'peak_amplitude', color: '#3b82f6', label: 'Peak |u| (m)', yAxisId: 'left' },
      { key: 'resonance_ratio', color: '#f59e0b', label: 'Amplification (×)', yAxisId: 'right' }
    ],
    extraMetrics: [
      { key: 'n_mode', label: 'Nearest Mode n', color: '#a855f7' },
      { key: 'f_mode', label: 'f_n theory (Hz)', color: '#10b981' },
      { key: 'wavelength', label: 'λ = c/f (m)', color: '#0ea5e9' },
      { key: 'detuning', label: 'Detuning (Δf/f)', color: '#ef4444' }
    ]
  }
];
