# data_manager.py
import json
import os
import requests
import base64
from datetime import datetime

class GitHubDataManager:
    """
    Gère la sauvegarde et le chargement automatique des données du bot
    sur un dépôt GitHub (via l'API).
    """

    def __init__(self, repo_owner, repo_name, file_path="bot_data.json", branch="main"):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.file_path = file_path
        self.branch = branch
        self.token = os.getenv("GITHUB_TOKEN")

        if not self.token:
            raise ValueError("❌ Variable d'environnement GITHUB_TOKEN non trouvée !")

        self.api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}"
        self.headers = {"Authorization": f"token {self.token}"}
        self.data = self.load_data()

    def load_data(self):
        """Charge les données depuis GitHub"""
        r = requests.get(self.api_url, headers=self.headers)
        if r.status_code == 200:
            content = r.json()["content"]
            decoded = base64.b64decode(content).decode("utf-8")
            try:
                return json.loads(decoded)
            except json.JSONDecodeError:
                print("⚠️ Fichier JSON corrompu, initialisation d'une structure vide.")
        else:
            print(f"⚠️ Impossible de charger le fichier (code {r.status_code}) — création d'une base vide.")
        return {"economy": {}, "warnings": {}, "levels": {}, "config": {}}

    def _save(self, message="Sauvegarde automatique du bot"):
        """Envoie le JSON sur GitHub (commit automatique)"""
        data_str = json.dumps(self.data, indent=4)
        encoded = base64.b64encode(data_str.encode()).decode()

        # Récupère le SHA du fichier (obligatoire pour PUT)
        sha = None
        r = requests.get(self.api_url, headers=self.headers)
        if r.status_code == 200:
            sha = r.json().get("sha")

        payload = {
            "message": message,
            "content": encoded,
            "branch": self.branch,
            "sha": sha
        }
        res = requests.put(self.api_url, headers=self.headers, json=payload)
        if res.status_code not in (200, 201):
            print(f"❌ Erreur GitHub ({res.status_code}): {res.text}")

    # === WARNINGS ===
    def add_warning(self, user_id, moderator_id, reason):
        uid = str(user_id)
        mid = str(moderator_id)
        if "warnings" not in self.data:
            self.data["warnings"] = {}
        if uid not in self.data["warnings"]:
            self.data["warnings"][uid] = []
        warn = {
            "id": len(self.data["warnings"][uid]) + 1,
            "timestamp": datetime.now().isoformat(),
            "moderator_id": mid,
            "reason": reason
        }
        self.data["warnings"][uid].append(warn)
        self._save("Ajout d'un avertissement")
        return warn

    def get_warnings(self, user_id):
        return self.data.get("warnings", {}).get(str(user_id), [])

    def remove_warning(self, user_id, warn_id):
        uid = str(user_id)
        if uid in self.data.get("warnings", {}):
            before = len(self.data["warnings"][uid])
            self.data["warnings"][uid] = [w for w in self.data["warnings"][uid] if w["id"] != warn_id]
            if len(self.data["warnings"][uid]) != before:
                self._save("Suppression d'un avertissement")
                return True
        return False

    # === ECONOMIE ===
    def get_balance(self, user_id):
        return self.data.get("economy", {}).get(str(user_id), {}).get("balance", 0)

    def update_balance(self, user_id, amount):
        uid = str(user_id)
        eco = self.data.setdefault("economy", {}).setdefault(uid, {"balance": 0})
        eco["balance"] += amount
        self._save("Mise à jour balance")
        return eco["balance"]

    def set_balance(self, user_id, amount):
        uid = str(user_id)
        eco = self.data.setdefault("economy", {}).setdefault(uid, {"balance": 0})
        eco["balance"] = amount
        self._save("Définition balance")
        return eco["balance"]

    # === LEVELING ===
    def add_xp(self, user_id, amount):
        uid = str(user_id)
        lvl = self.data.setdefault("levels", {}).setdefault(uid, {"xp": 0, "level": 0})
        lvl["xp"] += amount
        while lvl["xp"] >= self.required_xp(lvl["level"] + 1):
            lvl["level"] += 1
            lvl["xp"] -= self.required_xp(lvl["level"])
        self._save("Gain d'XP")
        return lvl["level"]

    def get_level_info(self, user_id):
        data = self.data.get("levels", {}).get(str(user_id), {"level": 0, "xp": 0})
        return data["level"], data["xp"]

    @staticmethod
    def required_xp(level):
        return 5 * level ** 2 + 50 * level + 100
