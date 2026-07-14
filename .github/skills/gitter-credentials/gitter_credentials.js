/**
 * Gitter Credentials Loader (JavaScript)
 * =========================================
 * Loads and validates Git credentials from .env configuration files.
 * 
 * Usage:
 *   const { CredentialsLoader } = require('./gitter_credentials.js');
 *   
 *   const loader = new CredentialsLoader();
 *   const credentials = loader.load('dev');
 *   console.log(credentials.git_user_name);
 */

const fs = require('fs');
const path = require('path');


class CredentialError extends Error {
    constructor(message) {
        super(message);
        this.name = 'CredentialError';
    }
}


class AuthMethod {
    static SSH = 'ssh';
    static HTTPS = 'https';
    static AUTO = 'auto';
    
    static isValid(value) {
        return [this.SSH, this.HTTPS, this.AUTO].includes(value);
    }
}


class GitCredentials {
    constructor({
        git_user_name,
        git_user_email,
        auth_method,
        github_token = null,
        ssh_key_path = null,
        ssh_passphrase = null,
        gpg_signing_enabled = false,
        gpg_key_id = null,
        gpg_signing_key_path = null,
        environment_profile = 'dev'
    }) {
        this.git_user_name = git_user_name;
        this.git_user_email = git_user_email;
        this.auth_method = auth_method;
        this.github_token = github_token;
        this.ssh_key_path = ssh_key_path;
        this.ssh_passphrase = ssh_passphrase;
        this.gpg_signing_enabled = gpg_signing_enabled;
        this.gpg_key_id = gpg_key_id;
        this.gpg_signing_key_path = gpg_signing_key_path;
        this.environment_profile = environment_profile;
    }
    
    toObject() {
        return {
            git_user_name: this.git_user_name,
            git_user_email: this.git_user_email,
            auth_method: this.auth_method,
            github_token: this.github_token ? '***REDACTED***' : null,
            ssh_key_path: this.ssh_key_path,
            ssh_passphrase: this.ssh_passphrase ? '***REDACTED***' : null,
            gpg_signing_enabled: this.gpg_signing_enabled,
            gpg_key_id: this.gpg_key_id,
            environment_profile: this.environment_profile,
        };
    }
}


class CredentialsLoader {
    constructor(projectRoot = process.cwd()) {
        this.projectRoot = projectRoot;
        this.envFile = path.join(projectRoot, '.env');
        this.envTemplate = path.join(projectRoot, '.env.template');
    }
    
    /**
     * Load and validate credentials for specified profile
     * @param {string} profile - Profile name (dev, staging, prod)
     * @returns {GitCredentials} Validated credentials
     * @throws {CredentialError} If validation fails
     */
    load(profile = 'dev') {
        // Load base configuration
        const baseConfig = this._loadEnvFile(this.envFile);
        
        // Load profile-specific overrides
        if (profile !== 'dev') {
            const profileFile = path.join(this.projectRoot, `.env.${profile}`);
            if (fs.existsSync(profileFile)) {
                const profileConfig = this._loadEnvFile(profileFile);
                Object.assign(baseConfig, profileConfig);
            }
        }
        
        // Validate and return
        return this._validateCredentials(baseConfig);
    }
    
    /**
     * Load environment variables from .env file
     * @private
     */
    _loadEnvFile(envPath) {
        if (!fs.existsSync(envPath)) {
            throw new CredentialError(`Environment file not found: ${envPath}`);
        }
        
        const config = {};
        try {
            const content = fs.readFileSync(envPath, 'utf8');
            const lines = content.split('\n');
            
            for (const line of lines) {
                const trimmed = line.trim();
                
                // Skip empty lines and comments
                if (!trimmed || trimmed.startsWith('#')) {
                    continue;
                }
                
                // Parse key=value
                const eqIndex = trimmed.indexOf('=');
                if (eqIndex > 0) {
                    const key = trimmed.substring(0, eqIndex).trim();
                    const value = trimmed.substring(eqIndex + 1).trim();
                    config[key] = value;
                }
            }
        } catch (error) {
            throw new CredentialError(`Failed to parse ${envPath}: ${error.message}`);
        }
        
        return config;
    }
    
    /**
     * Validate credential configuration
     * @private
     */
    _validateCredentials(config) {
        const errors = [];
        
        // Required fields
        const gitUserName = (config.GIT_USER_NAME || '').trim();
        const gitUserEmail = (config.GIT_USER_EMAIL || '').trim();
        
        if (!gitUserName) {
            errors.push('GIT_USER_NAME is required');
        }
        
        if (!gitUserEmail) {
            errors.push('GIT_USER_EMAIL is required');
        } else if (!gitUserEmail.includes('@')) {
            errors.push('GIT_USER_EMAIL must be a valid email address');
        }
        
        // Authentication method
        let authMethod = (config.GITHUB_AUTH_METHOD || 'ssh').toLowerCase();
        if (!AuthMethod.isValid(authMethod)) {
            errors.push(
                `GITHUB_AUTH_METHOD must be 'ssh', 'https', or 'auto', got '${authMethod}'`
            );
            authMethod = AuthMethod.SSH;
        }
        
        // GitHub token (HTTPS method)
        const githubToken = (config.GITHUB_TOKEN || '').trim() || null;
        if ([AuthMethod.HTTPS, AuthMethod.AUTO].includes(authMethod)) {
            if (!githubToken) {
                errors.push(
                    'GITHUB_TOKEN required for HTTPS auth method. ' +
                    'Create at https://github.com/settings/tokens'
                );
            }
        }
        
        // SSH configuration
        let sshKeyPath = (config.GITHUB_SSH_KEY_PATH || '').trim() || null;
        const sshPassphrase = (config.GITHUB_SSH_PASSPHRASE || '').trim() || null;
        
        if ([AuthMethod.SSH, AuthMethod.AUTO].includes(authMethod)) {
            if (!sshKeyPath) {
                errors.push('GITHUB_SSH_KEY_PATH required for SSH auth method');
            } else {
                // Expand ~ to home directory
                const expandedPath = sshKeyPath.replace('~', require('os').homedir());
                if (!fs.existsSync(expandedPath)) {
                    errors.push(
                        `SSH key not found: ${sshKeyPath} (expanded: ${expandedPath})`
                    );
                } else {
                    // Check permissions (should be 600 for security)
                    try {
                        const stats = fs.statSync(expandedPath);
                        const mode = stats.mode & parseInt('0777', 8);
                        if (mode !== parseInt('0600', 8)) {
                            errors.push(
                                `SSH key permissions incorrect (${mode.toString(8)}, should be 600). ` +
                                `Run: chmod 600 ${sshKeyPath}`
                            );
                        }
                    } catch (error) {
                        errors.push(`Failed to check SSH key permissions: ${error.message}`);
                    }
                }
            }
        }
        
        // GPG configuration
        const gpgSigningEnabledStr = (config.GPG_SIGNING_ENABLED || 'false').toLowerCase();
        const gpgSigningEnabled = ['true', '1', 'yes'].includes(gpgSigningEnabledStr);
        
        const gpgKeyId = (config.GPG_KEY_ID || '').trim() || null;
        const gpgSigningKeyPath = (config.GPG_SIGNING_KEY_PATH || '').trim() || null;
        
        if (gpgSigningEnabled && !gpgKeyId) {
            errors.push(
                'GPG_KEY_ID required when GPG_SIGNING_ENABLED=true. ' +
                'Get ID: gpg --list-secret-keys --keyid-format LONG'
            );
        }
        
        // Environment profile
        const environmentProfile = (config.ENVIRONMENT_PROFILE || 'dev').trim();
        if (!['dev', 'staging', 'prod'].includes(environmentProfile)) {
            errors.push(
                `ENVIRONMENT_PROFILE must be 'dev', 'staging', or 'prod', ` +
                `got '${environmentProfile}'`
            );
        }
        
        // Throw errors if any
        if (errors.length > 0) {
            const errorMsg = 'Credential validation failed:\n  ' + errors.join('\n  ');
            throw new CredentialError(errorMsg);
        }
        
        return new GitCredentials({
            git_user_name: gitUserName,
            git_user_email: gitUserEmail,
            auth_method: authMethod,
            github_token: githubToken,
            ssh_key_path: sshKeyPath,
            ssh_passphrase: sshPassphrase,
            gpg_signing_enabled: gpgSigningEnabled,
            gpg_key_id: gpgKeyId,
            gpg_signing_key_path: gpgSigningKeyPath,
            environment_profile: environmentProfile,
        });
    }
    
    /**
     * Validate credentials without throwing exceptions
     */
    validate(profile = 'dev') {
        try {
            this.load(profile);
            return {
                valid: true,
                message: 'Credentials validated successfully'
            };
        } catch (error) {
            return {
                valid: false,
                message: error.message
            };
        }
    }
    
    /**
     * Get human-readable credential summary
     */
    getSummary(profile = 'dev') {
        try {
            const creds = this.load(profile);
            const summary = `
Gitter Credentials Summary
==========================
Profile: ${creds.environment_profile}
Git User: ${creds.git_user_name} <${creds.git_user_email}>
Auth Method: ${creds.auth_method}

SSH Configuration:
  Path: ${creds.ssh_key_path || 'Not configured'}
  Passphrase: ${creds.ssh_passphrase ? 'Set' : 'Not set'}

GitHub Token: ${creds.github_token ? 'Configured' : 'Not configured'}

GPG Signing: ${creds.gpg_signing_enabled ? 'Enabled' : 'Disabled'}
  Key ID: ${creds.gpg_key_id || 'Not configured'}

Status: ✓ Valid
            `;
            return summary.trim();
        } catch (error) {
            return `Credentials Invalid:\n${error.message}`;
        }
    }
}


// Export for use as module
module.exports = {
    CredentialsLoader,
    GitCredentials,
    AuthMethod,
    CredentialError
};


// CLI usage for testing
if (require.main === module) {
    try {
        const loader = new CredentialsLoader();
        const profile = process.argv[2] || 'dev';
        
        console.log(`\nLoading credentials for profile: ${profile}`);
        console.log(loader.getSummary(profile));
        
        // Also print full config (redacted)
        const credentials = loader.load(profile);
        console.log('\nFull Configuration:');
        console.log(JSON.stringify(credentials.toObject(), null, 2));
        
    } catch (error) {
        console.error(`\n✗ Error: ${error.message}`);
        process.exit(1);
    }
}
