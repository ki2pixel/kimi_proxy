export default {
  // Restreint explicitement la découverte des tests à notre dossier local.
  // Pourquoi: éviter de scanner des snapshots/fixtures dans `research/`.
  roots: ['<rootDir>/tests/unit'],

  // Force le mode non-CI (certaines plateformes exportent CI=1 et Jest devient strict
  // sur les snapshots "obsolètes").
  ci: false,

  testEnvironment: 'jsdom',
  transform: {
    '^.+\\.js$': ['babel-jest', { configFile: './babel.config.cjs' }]
  },
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.js$': '$1',
  },
  modulePathIgnorePatterns: [
    '<rootDir>/research/'
  ],
  coverageReporters: ['text', 'json', 'lcov', 'html'],
  collectCoverageFrom: [
    'static/js/modules/**/*.js',
    '!static/js/modules/**/*.test.js',
    '!**/node_modules/**'
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80
    }
  },
  testMatch: [
    '**/tests/unit/**/*.test.js',
    '**/tests/unit/**/*.test.mjs'
  ],
  testPathIgnorePatterns: [
    '/node_modules/',
    '/tests/integration/'
  ]
};
