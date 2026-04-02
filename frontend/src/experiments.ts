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
    title: 'Conservation of Energy (Ballistic Pendulum)',
    description: 'Measure projectile velocity through energy conservation in ballistic pendulum. (Coming Soon)',
    thumbnail: 'https://picsum.photos/seed/ballistic/400/225',
    usdPath: 'Experiment/exp.usd',
    experimentNumber: '3',
    difficulty: 'Medium',
    isLocked: true,
    controls: [
      { id: 'projectile_mass', label: 'Projectile Mass (kg)', type: 'slider', min: 0.01, max: 0.5, step: 0.01, defaultValue: 0.05, command: 'set_projectile_mass' },
      { id: 'pendulum_mass', label: 'Pendulum Mass (kg)', type: 'slider', min: 0.5, max: 5, step: 0.1, defaultValue: 2.0, command: 'set_pendulum_mass' },
      { id: 'run', label: 'Fire', type: 'button', command: 'start_simulation' },
      { id: 'reset', label: 'Reset', type: 'button', command: 'reset' }
    ],
    chartConfig: [
      { key: 'velocity', color: '#00f3ff', label: 'Velocity (m/s)', yAxisId: 'left' },
      { key: 'energy', color: '#ff4444', label: 'Energy (J)', yAxisId: 'right' }
    ]
  },
  {
    id: 'exp-04-driven-damped-oscillation',
    title: 'Driven Damped Harmonic Oscillations',
    description: 'Study resonance and phase relationships in driven damped oscillators. (Coming Soon)',
    thumbnail: 'https://picsum.photos/seed/oscillation/400/225',
    usdPath: 'Experiment/exp.usd',
    experimentNumber: '4',
    difficulty: 'Medium',
    isLocked: true,
    controls: [
      { id: 'damping', label: 'Damping Coefficient', type: 'slider', min: 0, max: 2, step: 0.1, defaultValue: 0.5, command: 'set_damping' },
      { id: 'drive_frequency', label: 'Drive Frequency (Hz)', type: 'slider', min: 0.1, max: 5, step: 0.1, defaultValue: 1.0, command: 'set_frequency' },
      { id: 'run', label: 'Run', type: 'button', command: 'start_simulation' },
      { id: 'reset', label: 'Reset', type: 'button', command: 'reset' }
    ],
    chartConfig: [
      { key: 'displacement', color: '#D4AF37', label: 'Displacement (m)', yAxisId: 'left' },
      { key: 'amplitude', color: '#888888', label: 'Amplitude', yAxisId: 'right' }
    ]
  },
  {
    id: 'exp-05-rotational-inertia',
    title: 'Rotational Inertia (Physical Pendulum)',
    description: 'Determine rotational inertia through physical pendulum period measurements. (Coming Soon)',
    thumbnail: 'https://picsum.photos/seed/inertia/400/225',
    usdPath: 'Experiment/exp.usd',
    experimentNumber: '5',
    difficulty: 'Medium',
    isLocked: true,
    controls: [
      { id: 'pivot_position', label: 'Pivot Position (cm)', type: 'slider', min: 5, max: 50, step: 1, defaultValue: 25, command: 'set_pivot' },
      { id: 'angle', label: 'Initial Angle (°)', type: 'slider', min: 5, max: 30, step: 1, defaultValue: 10, command: 'set_angle' },
      { id: 'run', label: 'Run', type: 'button', command: 'start_simulation' },
      { id: 'reset', label: 'Reset', type: 'button', command: 'reset' }
    ],
    chartConfig: [
      { key: 'period', color: '#a855f7', label: 'Period (s)', yAxisId: 'left' },
      { key: 'inertia', color: '#00f3ff', label: 'Moment of Inertia', yAxisId: 'right' }
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
    description: 'Study standing waves and resonance frequencies in air columns. (Coming Soon)',
    thumbnail: 'https://picsum.photos/seed/resonance/400/225',
    usdPath: 'Experiment/exp.usd',
    experimentNumber: '8',
    difficulty: 'Medium',
    isLocked: true,
    controls: [
      { id: 'length', label: 'Column Length (cm)', type: 'slider', min: 10, max: 100, step: 1, defaultValue: 50, command: 'set_length' },
      { id: 'frequency', label: 'Frequency (Hz)', type: 'slider', min: 100, max: 2000, step: 50, defaultValue: 512, command: 'set_frequency' },
      { id: 'run', label: 'Generate Tone', type: 'button', command: 'start_simulation' },
      { id: 'reset', label: 'Reset', type: 'button', command: 'reset' }
    ],
    chartConfig: [
      { key: 'amplitude', color: '#ec4899', label: 'Sound Amplitude', yAxisId: 'left' },
      { key: 'resonance_peaks', color: '#ffffff', label: 'Resonance Peaks', yAxisId: 'right' }
    ]
  }
];
