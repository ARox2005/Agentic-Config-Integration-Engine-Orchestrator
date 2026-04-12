pipeline {
    // This tells Jenkins it can run on any available server agent
    agent any 

    // We tell Jenkins to use NodeJS version 18 so it can run npm commands
    tools { 
        nodejs 'NodeJS' 
    }
    
    stages {
        // Stage 1: Download your code from GitHub to the Jenkins server
        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }
        
        // Stage 2: Install Playwright and its browser dependencies
        stage('Install QA Dependencies') {
            steps {
                dir('e2e-tests') {
                    sh 'npm install'
                    sh 'npx playwright install --with-deps'
                }
            }
        }
        
        // Stage 3: Run the automated tests you just wrote!
        stage('Execute Playwright Tests') {
            steps {
                dir('e2e-tests') {
                    // We run headless mode on servers (no visual browser opens)
                    sh 'npx playwright test'
                }
            }
        }
    }
    
    // Stage 4: What to do after tests finish (save the report)
    post {
        always {
            // This saves the HTML report so your team can view it on the Jenkins web dashboard
            archiveArtifacts artifacts: 'e2e-tests/playwright-report/**/*', allowEmptyArchive: true
        }
    }
}
