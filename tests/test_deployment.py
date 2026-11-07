import unittest

from config import resolve_paths


class DeploymentPathTests(unittest.TestCase):
    def test_frozen_build_keeps_saves_in_user_data_folder(self):
        root, save_dir = resolve_paths(
            True,
            r"C:\Games\MATHMON\MATHMON.exe",
            r"C:\source\mathmon\config.py",
            r"C:\Users\Player\AppData\Local",
        )
        self.assertEqual(str(root), r"C:\Games\MATHMON")
        self.assertEqual(str(save_dir), r"C:\Users\Player\AppData\Local\MATHMON\saves")

    def test_development_saves_remain_in_project_folder(self):
        root, save_dir = resolve_paths(False, "", r"C:\source\mathmon\config.py")
        self.assertEqual(save_dir, root / "saves")


if __name__ == "__main__":
    unittest.main()
