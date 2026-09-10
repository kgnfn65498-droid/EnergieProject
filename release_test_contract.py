"""Single source of truth for assertions about the current release candidate.

Historical test fixtures keep their historical version values. Tests that verify the
currently built candidate import these constants instead of being rewritten per release.
"""
CURRENT_RELEASE = "32.4.35"
CURRENT_PM_VERSION = "2.0.0-rc22"
