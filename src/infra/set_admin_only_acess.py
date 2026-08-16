import os
import platform
import stat
# import win32security
# import ntsecuritycon as con
import logging

logging.basicConfig(level=logging.CRITICAL+1, format='%(asctime)s %(levelname)s:%(message)s')
logger = logging.getLogger(__name__)


def set_admin_only_access(folder_path):
    # Check if the folder exists
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Folder {folder_path} does not exist")

    system = platform.system()

    if system == "Windows":
        try:
            import win32security
            import ntsecuritycon as con

            # Get the SID of the Administrators group
            # admin_sid = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid)
            admin_sid = win32security.CreateWellKnownSid(win32security.WinBuiltinAdministratorsSid)

            # Get the security object for the folder
            sd = win32security.GetFileSecurity(folder_path, win32security.DACL_SECURITY_INFORMATION)

            # Create a new DACL (access control list)
            dacl = win32security.ACL()

            # Add rule: only administrators have full access
            dacl.AddAccessAllowedAce(win32security.ACL_REVISION, con.FILE_ALL_ACCESS, admin_sid)

            # Set the new DACL for the folder
            sd.SetSecurityDescriptorDacl(1, dacl, 0)
            win32security.SetFileSecurity(folder_path, win32security.DACL_SECURITY_INFORMATION, sd)
            logger.debug(f"Access rights for {folder_path} on Windows successfully set (administrators only).")

        except ImportError:
            raise ImportError("Windows requires the pywin32 library: 'pip install pywin32'")
        except Exception as e:
            raise Exception(f"Error setting rights on Windows: {e}")

    elif system == "Linux" or system == "Darwin":  # Darwin is macOS
        try:
            # Set owner to root
            os.chown(folder_path, 0, 0)  # 0, 0 are UID and GID for root

            # Set access rights: only owner (root) has access
            os.chmod(folder_path, stat.S_IRWXU)  # 700 — only owner can read/write/execute
            logger.debug(f"Access rights for {folder_path} on {system} successfully set (root only).")

        except PermissionError:
            raise PermissionError("Run the script with superuser privileges (sudo) for Linux/macOS")
        except Exception as e:
            raise Exception(f"Error setting rights on {system}: {e}")

    else:
        raise NotImplementedError(f"Operating system {system} is not supported")
    
    
# def set_admin_only_access(file_or_folder_path):
#     if not os.path.exists(file_or_folder_path):
#         raise FileNotFoundError(f"Object {file_or_folder_path} does not exist")

#     system = platform.system()

#     if system == "Windows":
#         try:
#             # Get the SID of the Administrators group
#             admin_sid = win32security.CreateWellKnownSid(win32security.WinBuiltinAdministratorsSid)
#             # Get the SYSTEM SID
#             system_sid = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid)

#             # Get the security object
#             sd = win32security.GetFileSecurity(file_or_folder_path, win32security.DACL_SECURITY_INFORMATION)
            
#             # Create a new DACL
#             dacl = win32security.ACL()

#             # Add rights for the Administrators group
#             dacl.AddAccessAllowedAce(win32security.ACL_REVISION, con.FILE_ALL_ACCESS, admin_sid)
#             # Add rights for SYSTEM
#             dacl.AddAccessAllowedAce(win32security.ACL_REVISION, con.FILE_ALL_ACCESS, system_sid)

#             # Set the new DACL
#             sd.SetSecurityDescriptorDacl(1, dacl, 0)
#             win32security.SetFileSecurity(file_or_folder_path, win32security.DACL_SECURITY_INFORMATION, sd)
#             print(f"Access rights for {file_or_folder_path} on Windows successfully set (administrators and SYSTEM only).")

#         except ImportError:
#             raise ImportError("Windows requires the pywin32 library: 'pip install pywin32'")
#         except Exception as e:
#             raise Exception(f"Error setting rights on Windows: {e}")
#     elif system == "Linux" or system == "Darwin":  # Darwin is macOS
#         try:
#             # Set owner to root
#             os.chown(file_or_folder_path, 0, 0)  # 0, 0 are UID and GID for root

#             # Set access rights: only owner (root) has access
#             os.chmod(file_or_folder_path, stat.S_IRWXU)  # 700 — only owner can read/write/execute
#             print(f"Access rights for {file_or_folder_path} on {system} successfully set (root only).")

#         except PermissionError:
#             raise PermissionError("Run the script with superuser privileges (sudo) for Linux/macOS")
#         except Exception as e:
#             raise Exception(f"Error setting rights on {system}: {e}")

#     else:
#         raise NotImplementedError(f"Operating system {system} is not supported")

# # Usage example
# if __name__ == "__main__":
#     folder_path = r"C:\path\to\your\folder" if platform.system() == "Windows" else "/path/to/your/folder"
#     try:
#         set_admin_only_access(folder_path)
#     except Exception as e:
#         print(f"Error: {e}")