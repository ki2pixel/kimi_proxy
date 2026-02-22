export default {
  testEnvironment: 'jsdom',
  transform: {},
  extensionsToTreatAsEsm: ['.js'],
  moduleNameMapping: {
    '^(\\.{1,2}/.*)\\.js$': '$1',
  },
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
  ]
};
