module.exports = {
    verbose: true,
    preset: 'jest-playwright-preset',
    testRunner : 'jest-jasmine2',
    transformIgnorePatterns: ['node_modules/(?!(@patternfly/react-icons/dist/esm/icons/help-icon)/)'],
    transform:{
        "^.+\\.js?$": "js-jest",
    },
    reporters: ["default", "jest-allure"],
    moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json', 'node'],
    setupFilesAfterEnv: ['jest-allure/dist/setup','expect-playwright'],
    testMatch: [
        "**/tests/**/*.spec.(js|jsx|ts|tsx)",
        // "**/tests/**/*.test.(js|jsx|ts|tsx)"
    ]
};