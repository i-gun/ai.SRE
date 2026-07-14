"""
Gitter Credentials Loader
==========================
Loads and validates Git credentials from .env configuration files.

Usage:
    from gitter_credentials import CredentialsLoader, CredentialError
    
    try:
        loader = CredentialsLoader()
        creds = loader.load(profile='dev')
        print(f"Git User: {creds['git_user_name']}")
    except CredentialError as e:
        print(f"Error: {e}")
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum


class AuthMethod(Enum):
    """GitHub authentication method"""
    SSH = "ssh"
    HTTPS = "https"
    AUTO = "auto"


@dataclass
class GitCredentials:
    """Validated Git credentials container"""
    git_user_name: str
    git_user_email: str
    auth_method: AuthMethod
    github_token: Optional[str] = None
    ssh_key_path: Optional[str] = None
    ssh_passphrase: Optional[str] = None
    gpg_signing_enabled: bool = False
    gpg_key_id: Optional[str] = None
    gpg_signing_key_path: Optional[str] = None
    environment_profile: str = "dev"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values and sensitive data"""
        return {
            "git_user_name": self.git_user_name,
            "git_user_email": self.git_user_email,
            "auth_method": self.auth_method.value,
            "github_token": "***REDACTED***" if self.github_token else None,
            "ssh_key_path": self.ssh_key_path,
            "ssh_passphrase": "***REDACTED***" if self.ssh_passphrase else None,
            "gpg_signing_enabled": self.gpg_signing_enabled,
            "gpg_key_id": self.gpg_key_id,
            "environment_profile": self.environment_profile,
        }


class CredentialError(Exception):
    """Credential loading/validation error"""
    pass


class CredentialsLoader:
    """Load and validate Git credentials from .env files"""
    
    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize credentials loader
        
        Args:
            project_root: Path to project root (defaults to current directory)
        """
        self.project_root = Path(project_root or os.getcwd())
        self.env_file = self.project_root / ".env"
        self.env_template = self.project_root / ".env.template"
    
    def load(self, profile: str = "dev") -> GitCredentials:
        """
        Load and validate credentials for specified profile
        
        Args:
            profile: Profile name (dev, staging, prod)
            
        Returns:
            GitCredentials: Validated credentials object
            
        Raises:
            CredentialError: If validation fails
        """
        # Load base configuration
        base_config = self._load_env_file(self.env_file)
        
        # Load profile-specific overrides
        if profile != "dev":
            profile_file = self.project_root / f".env.{profile}"
            if profile_file.exists():
                profile_config = self._load_env_file(profile_file)
                base_config.update(profile_config)
        
        # Validate configuration
        return self._validate_credentials(base_config)
    
    def _load_env_file(self, env_path: Path) -> Dict[str, str]:
        """
        Load environment variables from .env file
        
        Args:
            env_path: Path to .env file
            
        Returns:
            Dictionary of key-value pairs
            
        Raises:
            CredentialError: If file not found
        """
        if not env_path.exists():
            raise CredentialError(f".env file not found: {env_path}")
        
        config = {}
        try:
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse key=value
                    if '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
        except Exception as e:
            raise CredentialError(f"Failed to parse {env_path}: {e}")
        
        return config
    
    def _validate_credentials(self, config: Dict[str, str]) -> GitCredentials:
        """
        Validate credential configuration
        
        Args:
            config: Configuration dictionary
            
        Returns:
            GitCredentials: Validated credentials
            
        Raises:
            CredentialError: If validation fails
        """
        errors = []
        
        # Required fields
        git_user_name = config.get('GIT_USER_NAME', '').strip()
        git_user_email = config.get('GIT_USER_EMAIL', '').strip()
        
        if not git_user_name:
            errors.append("GIT_USER_NAME is required")
        
        if not git_user_email:
            errors.append("GIT_USER_EMAIL is required")
        elif '@' not in git_user_email:
            errors.append("GIT_USER_EMAIL must be a valid email address")
        
        # Authentication method
        auth_method_str = config.get('GITHUB_AUTH_METHOD', 'ssh').lower()
        try:
            auth_method = AuthMethod(auth_method_str)
        except ValueError:
            errors.append(
                f"GITHUB_AUTH_METHOD must be 'ssh', 'https', or 'auto', "
                f"got '{auth_method_str}'"
            )
            auth_method = AuthMethod.SSH
        
        # GitHub token (HTTPS method)
        github_token = config.get('GITHUB_TOKEN', '').strip() or None
        if auth_method in [AuthMethod.HTTPS, AuthMethod.AUTO]:
            if not github_token:
                errors.append(
                    "GITHUB_TOKEN required for HTTPS auth method. "
                    "Create at https://github.com/settings/tokens"
                )
        
        # SSH configuration
        ssh_key_path = config.get('GITHUB_SSH_KEY_PATH', '').strip() or None
        ssh_passphrase = config.get('GITHUB_SSH_PASSPHRASE', '').strip() or None
        
        if auth_method in [AuthMethod.SSH, AuthMethod.AUTO]:
            if not ssh_key_path:
                errors.append("GITHUB_SSH_KEY_PATH required for SSH auth method")
            else:
                # Expand ~ to home directory
                expanded_path = Path(ssh_key_path).expanduser()
                if not expanded_path.exists():
                    errors.append(
                        f"SSH key not found: {ssh_key_path} (expanded: {expanded_path})"
                    )
                # Check permissions (should be 600 for security)
                if expanded_path.exists():
                    mode = expanded_path.stat().st_mode
                    if mode & 0o077:  # Check if other/group have access
                        errors.append(
                            f"SSH key permissions too open. "
                            f"Run: chmod 600 {ssh_key_path}"
                        )
        
        # GPG configuration
        gpg_signing_enabled_str = config.get('GPG_SIGNING_ENABLED', 'false').lower()
        gpg_signing_enabled = gpg_signing_enabled_str in ['true', '1', 'yes']
        
        gpg_key_id = config.get('GPG_KEY_ID', '').strip() or None
        gpg_signing_key_path = config.get('GPG_SIGNING_KEY_PATH', '').strip() or None
        
        if gpg_signing_enabled and not gpg_key_id:
            errors.append(
                "GPG_KEY_ID required when GPG_SIGNING_ENABLED=true. "
                "Get ID: gpg --list-secret-keys --keyid-format LONG"
            )
        
        # Environment profile
        environment_profile = config.get('ENVIRONMENT_PROFILE', 'dev').strip()
        if environment_profile not in ['dev', 'staging', 'prod']:
            errors.append(
                f"ENVIRONMENT_PROFILE must be 'dev', 'staging', or 'prod', "
                f"got '{environment_profile}'"
            )
        
        # Raise errors if any
        if errors:
            error_msg = "Credential validation failed:\n  " + "\n  ".join(errors)
            raise CredentialError(error_msg)
        
        return GitCredentials(
            git_user_name=git_user_name,
            git_user_email=git_user_email,
            auth_method=auth_method,
            github_token=github_token,
            ssh_key_path=ssh_key_path,
            ssh_passphrase=ssh_passphrase,
            gpg_signing_enabled=gpg_signing_enabled,
            gpg_key_id=gpg_key_id,
            gpg_signing_key_path=gpg_signing_key_path,
            environment_profile=environment_profile,
        )
    
    def validate(self, profile: str = "dev") -> tuple[bool, str]:
        """
        Validate credentials without raising exceptions
        
        Args:
            profile: Profile name to validate
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            self.load(profile)
            return True, "Credentials validated successfully"
        except CredentialError as e:
            return False, str(e)
    
    def get_summary(self, profile: str = "dev") -> str:
        """
        Get human-readable credential summary
        
        Args:
            profile: Profile name
            
        Returns:
            Formatted summary string
        """
        try:
            creds = self.load(profile)
            summary = f"""
Gitter Credentials Summary
==========================
Profile: {creds.environment_profile}
Git User: {creds.git_user_name} <{creds.git_user_email}>
Auth Method: {creds.auth_method.value}

SSH Configuration:
  Path: {creds.ssh_key_path or "Not configured"}
  Passphrase: {"Set" if creds.ssh_passphrase else "Not set"}

GitHub Token: {"Configured" if creds.github_token else "Not configured"}

GPG Signing: {"Enabled" if creds.gpg_signing_enabled else "Disabled"}
  Key ID: {creds.gpg_key_id or "Not configured"}

Status: ✓ Valid
            """
            return summary.strip()
        except CredentialError as e:
            return f"Credentials Invalid:\n{e}"


# CLI usage for testing
if __name__ == "__main__":
    import sys
    
    try:
        loader = CredentialsLoader()
        profile = sys.argv[1] if len(sys.argv) > 1 else "dev"
        
        print(f"\nLoading credentials for profile: {profile}")
        print(loader.get_summary(profile))
        
        # Also print full config (redacted)
        creds = loader.load(profile)
        print("\nFull Configuration:")
        print(json.dumps(creds.to_dict(), indent=2))
        
    except CredentialError as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
