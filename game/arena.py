"""The Math Arena: competitive best-of-5 speed duels against AI players.

Both sides get the same question. The first correct answer scores the round; a rival that
answers wrong is locked out, so the player can still take it. First to 3 wins. Ratings move
with Elo, ranks run Bronze -> Champion, and first wins over each rival earn a trophy.
Every round ends by showing the right answer and why, so a lost round still teaches.
"""
import pygame

from ai.arena_agent import RIVALS, STYLES, ArenaRivalAgent, elo_change, rank_for
from config import PALETTE
from game import monster_sprites
from game.creatures import WILD_BY_NAME, creature_spec, draw_creature
from game.ui import heart, panel, text, wrapped
from mathematics import battle_puzzles
from mathematics.answer_validator import AnswerValidator
from mathematics.puzzles import evaluate_expression
from mathematics.question_generator import topic_label

WIN_SCORE = 3
ROUND_LIMIT = 40 * 60         # frames: a round nobody answers in 40 seconds scores for no one
MAX_ROUNDS = 9
COUNTDOWN = 200               # frames for 3-2-1-GO (50 each)
REVEAL = 150                  # frames showing each round's answer
PUZZLE_CHANCE = 1 / 3
RANK_COLORS = {"BRONZE": (205, 127, 50), "SILVER": (192, 200, 210), "GOLD": (242, 187, 82),
               "PLATINUM": (140, 230, 230), "CHAMPION": (190, 150, 255)}


class ArenaScreen:
    def __init__(self, repository, orchestrator, player, leader, avatar_sheet, rng):
        self.repository, self.orchestrator, self.player = repository, orchestrator, player
        self.leader, self.avatar_sheet, self.rng = leader, avatar_sheet, rng
        self.stats = repository.arena_stats(player.player_id)
        self.flags = set(repository.world_flags(player.player_id))
        friend = "LUNA" if avatar_sheet.endswith("ALEX") else "ALEX"
        self.rivals = [self._personalise(p, friend) for p in RIVALS]
        self.selected = self._suggested()
        self.state = "lobby"
        self.closed = False
        self.summary = ""
        self.frame = 0
        self.shake = 0  # update() runs every frame, including in the lobby before any round

    @staticmethod
    def _personalise(profile, friend):
        from dataclasses import replace
        return replace(profile, name=profile.name.replace("{friend}", friend.title()),
                       sheet=profile.sheet.replace("{friend_upper}", friend))

    def _suggested(self):
        """The first rival you haven't beaten yet - the next rung of the ladder."""
        for index, rival in enumerate(self.rivals):
            if f"arena_beaten:{rival.rival_id}" not in self.flags:
                return index
        return len(self.rivals) - 1

    # ------------------------------------------------------------------ match flow
    def _start_match(self):
        self.rival = self.rivals[self.selected]
        self.agent = ArenaRivalAgent(self.rival, rng=self.rng)
        self.score = [0, 0]           # player, rival
        self.round = 0
        self.history = []             # "you" / "rival" / "none"
        self.confirm_forfeit = False
        self.rival_spec = WILD_BY_NAME.get(self.rival.monster) or creature_spec(self.rival.monster)
        self._next_round()

    def _next_round(self):
        self.round += 1
        result = self.orchestrator.next_question(self.player.player_id)
        question = result["question"]
        if self.rng.random() < PUZZLE_CHANCE:
            question = battle_puzzles.puzzle_for(question.topic, question.difficulty, self.rng) or question
        self.question = question
        self.plan = self.agent.plan(question, self.score[0] - self.score[1])
        self.rival_frames = 0
        self.rival_locked = False
        self.round_frames = 0
        self.answer = ""
        self.player_wrong = 0
        self.shake = 0
        self.message = ""
        self.winner = None
        self.state = "countdown"
        self.timer = COUNTDOWN

    def _finish_round(self, winner):
        self.winner = winner
        self.history.append(winner)
        if winner == "you":
            self.score[0] += 1
        elif winner == "rival":
            self.score[1] += 1
        self.state, self.timer = "reveal", REVEAL

    def _after_reveal(self):
        if max(self.score) >= WIN_SCORE or self.round >= MAX_ROUNDS:
            self._finish_match(self.score[0] > self.score[1])
        else:
            self._next_round()

    def _finish_match(self, won, forfeit=False):
        pid = self.player.player_id
        old_rating, old_rank = self.stats["rating"], rank_for(self.stats["rating"])
        change = elo_change(old_rating, self.rival.rating, won)
        stats = dict(self.stats)
        stats["rating"] = max(100, old_rating + change)
        if won:
            stats["wins"] += 1
            stats["streak"] += 1
            stats["best_streak"] = max(stats["best_streak"], stats["streak"])
        else:
            stats["losses"] += 1
            stats["streak"] = 0
        self.repository.save_arena_stats(pid, stats)
        self.stats = stats
        index = self.rivals.index(self.rival)
        exp = (20 + 5 * index) if won else (0 if forfeit else 6)
        rewards = [f"+{exp} EXP"] if exp else []
        trophy = f"arena_beaten:{self.rival.rival_id}"
        first_win = won and trophy not in self.flags
        if first_win:
            self.repository.set_world_flag(pid, trophy)
            self.flags.add(trophy)
            self.repository.add_item(pid, "Numeris Core", 1)
            rewards.append("TROPHY + Numeris Core")
            if self.rival.rival_id == "numeris":
                self.repository.set_world_flag(pid, "arena:champion")
                self.flags.add("arena:champion")
                rewards.append("CHAMPION TITLE")
        from game.team import Team
        team = Team(self.repository, self.player)
        member = team.leader()  # arena EXP goes to whoever leads your team
        leveled = member.add_exp(exp) if exp else False
        team.save(member)
        new_rank = rank_for(stats["rating"])
        self.result = {"won": won, "change": change, "old_rating": old_rating, "rating": stats["rating"],
                       "rank_up": new_rank != old_rank and stats["rating"] > old_rating, "rank": new_rank,
                       "rewards": rewards + (["LEVEL UP!"] if leveled else []), "forfeit": forfeit}
        verdict = "won" if won else "lost"
        self.summary = (f"Arena: you {verdict} vs {self.rival.name} {self.score[0]}-{self.score[1]}. "
                        f"Rating {stats['rating']} ({change:+d}).")
        self.state = "result"
        self.selected = self._suggested() if won else self.selected

    # ---------------------------------------------------------------------- input
    def handle_key(self, key, unicode=""):
        if self.state == "lobby":
            if key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(self.rivals)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.rivals)
            elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e):
                self._start_match()
            elif key == pygame.K_ESCAPE:
                self.closed = True
        elif self.state == "result":
            if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_e):
                self.state = "lobby"
        elif self.state == "reveal":
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                self.timer = 0
        elif self.state in ("countdown", "round"):
            if key == pygame.K_ESCAPE:
                if self.confirm_forfeit:
                    self.score[1] = WIN_SCORE
                    self._finish_match(False, forfeit=True)
                else:
                    self.confirm_forfeit = True
                    self.message = "Press ESC again to forfeit (counts as a loss)."
                return
            self.confirm_forfeit = False
            if self.state != "round":
                return
            allowed = "0123456789+-x*()" if self.question.format == "target" else "0123456789.-/"
            if key == pygame.K_BACKSPACE:
                self.answer = self.answer[:-1]
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.answer.strip():
                self._submit()
            elif unicode and unicode in allowed and len(self.answer) < 16:
                self.answer += unicode

    def _submit(self):
        submitted = self.answer
        if self.question.format == "target":
            value = evaluate_expression(self.answer, list(self.question.visual[1]))
            if value is None:
                self.answer, self.shake = "", 14
                self.message = "Use each number once with + − x."
                return
            submitted = str(value)
        correct = AnswerValidator.check(submitted, self.question.answer)
        self.orchestrator.submit_answer(self.player.player_id, self.question, submitted)  # learning data
        if correct:
            self._finish_round("you")
        else:
            self.player_wrong += 1
            self.answer, self.shake = "", 14
            self.message = "Not quite - keep going!" if not self.rival_locked else "Not quite - the round is still yours to take!"

    # --------------------------------------------------------------------- update
    def update(self):
        self.frame += 1
        if self.shake:
            self.shake -= 1
        if self.state == "countdown":
            self.timer -= 1
            if self.timer <= 0:
                self.state = "round"
        elif self.state == "round":
            self.round_frames += 1
            if not self.rival_locked:
                self.rival_frames += 1
                if self.rival_frames >= self.plan.think_seconds * 60:
                    if self.plan.correct:
                        self._finish_round("rival")
                        return
                    self.rival_locked = True
                    self.message = f"{self.rival.name} buzzed in with {self.plan.shown_answer}... WRONG! Your chance!"
            if self.round_frames >= ROUND_LIMIT:
                self._finish_round("none")
        elif self.state == "reveal":
            self.timer -= 1
            if self.timer <= 0:
                self._after_reveal()

    # ----------------------------------------------------------------------- draw
    def draw(self, surface, frame=0):
        surface.fill((22, 18, 40))
        for i in range(30):  # stadium lights
            x = (i * 37) % 320
            pygame.draw.rect(surface, (40, 34, 70), (x, (i * 13) % 30, 2, 2))
        getattr(self, f"_draw_{'match' if self.state in ('countdown', 'round', 'reveal') else self.state}")(surface, frame)

    def _rank_badge(self, surface, x, y, rating):
        rank = rank_for(rating)
        color = RANK_COLORS[rank]
        pygame.draw.polygon(surface, color, [(x, y + 2), (x + 6, y), (x + 12, y + 2), (x + 11, y + 10),
                                             (x + 6, y + 14), (x + 1, y + 10)])
        pygame.draw.polygon(surface, PALETTE["ink"], [(x, y + 2), (x + 6, y), (x + 12, y + 2), (x + 11, y + 10),
                                                      (x + 6, y + 14), (x + 1, y + 10)], 1)
        text(surface, rank, (x + 17, y + 2), 10, color)

    def _draw_lobby(self, surface, frame):
        text(surface, "MATH ARENA", (12, 6), 18, PALETTE["gold"])
        stats = self.stats
        panel(surface, (176, 4, 138, 34), PALETTE["night"], RANK_COLORS[rank_for(stats["rating"])])
        self._rank_badge(surface, 182, 9, stats["rating"])
        text(surface, f"{stats['rating']}", (308, 9), 11, PALETTE["white"], align="right")
        text(surface, f"W {stats['wins']}  L {stats['losses']}  STREAK {stats['streak']}", (182, 25), 8, PALETTE["cream"])
        text(surface, "Same question for both. First correct", (12, 24), 8, PALETTE["muted"])
        text(surface, "answer scores the round. First to 3!", (12, 32), 8, PALETTE["muted"])
        for index, rival in enumerate(self.rivals):
            y = 42 + index * 23
            chosen = index == self.selected
            beaten = f"arena_beaten:{rival.rival_id}" in self.flags
            panel(surface, (8, y, 304, 20), PALETTE["deep"] if chosen else PALETTE["night"],
                  PALETTE["gold"] if chosen else PALETTE["night"])
            spec = WILD_BY_NAME.get(rival.monster) or creature_spec(rival.monster)
            surface.set_clip((12, y + 2, 22, 16))
            draw_creature(surface, spec, (23, y + 19), 16, "idle", flip=True)
            surface.set_clip(None)
            text(surface, rival.name, (38, y + 3), 10, PALETTE["gold"] if chosen else PALETTE["white"])
            text(surface, rival.title, (38, y + 12), 7, PALETTE["muted"])
            text(surface, rival.style.upper(), (178, y + 7), 8, PALETTE["sky"])
            rank = rank_for(rival.rating)
            text(surface, f"{rival.rating}", (258, y + 7), 9, RANK_COLORS[rank], align="right")
            if beaten:
                heart(surface, 290, y + 6, PALETTE["mint"])
            elif index == self._suggested():
                text(surface, "NEXT", (306, y + 7), 7, PALETTE["coral"], align="right")
        rival = self.rivals[self.selected]
        panel(surface, (8, 182, 304, 34), PALETTE["night"], PALETTE["cream"])
        text(surface, f"{rival.name}:", (14, 186), 9, PALETTE["gold"])
        wrapped(surface, f"\"{rival.taunt}\"", (14, 196, 292, 18), 9, PALETTE["white"], 10, 2)
        text(surface, STYLES[rival.style][2], (306, 186), 8, PALETTE["muted"], align="right")
        text(surface, "UP/DOWN: PICK RIVAL     ENTER: CHALLENGE     ESC: LEAVE", (160, 228), 9, PALETTE["cream"],
             center=True)

    def _fighter(self, surface, x, sheet, spec, flip, pose):
        if sheet and monster_sprites.available(sheet):
            monster_sprites.draw(surface, sheet, (x, 86), 46, pose, flip=flip)
        draw_creature(surface, spec, (x + (-30 if flip else 30), 92), 34,
                      ("idle", "idle2", "idle3", "idle2")[(self.frame // 18) % 4], flip=flip)

    def _draw_match(self, surface, frame):
        rival = self.rival
        # Fighters: player on the left, rival on the right.
        pygame.draw.ellipse(surface, (40, 34, 70), (20, 82, 110, 16))
        pygame.draw.ellipse(surface, (40, 34, 70), (190, 82, 110, 16))
        you_pose = 5 if self.state == "reveal" and self.winner == "you" else 7 if self.state == "reveal" and self.winner == "rival" else 0
        rival_pose = 5 if self.state == "reveal" and self.winner == "rival" else 7 if self.state == "reveal" and self.winner == "you" else 0
        self._fighter(surface, 50, self.avatar_sheet, self.leader, False, you_pose)
        self._fighter(surface, 270, rival.sheet, self.rival_spec, True, rival_pose)
        # Scoreboard.
        panel(surface, (96, 4, 128, 30), PALETTE["night"], PALETTE["gold"])
        text(surface, f"{self.score[0]}  -  {self.score[1]}", (160, 18), 18, PALETTE["white"], center=True)
        text(surface, "YOU", (12, 6), 11, PALETTE["mint"])
        text(surface, rival.name, (308, 6), 11, PALETTE["coral"], align="right")
        for i in range(WIN_SCORE):
            pygame.draw.rect(surface, PALETTE["mint"] if i < self.score[0] else PALETTE["deep"], (12 + i * 10, 20, 7, 7))
            pygame.draw.rect(surface, PALETTE["coral"] if i < self.score[1] else PALETTE["deep"], (302 - i * 10, 20, 7, 7))
        text(surface, f"ROUND {self.round}", (160, 40), 9, PALETTE["muted"], center=True)
        # Rival thinking bar.
        progress = min(1.0, self.rival_frames / max(1, self.plan.think_seconds * 60))
        pygame.draw.rect(surface, PALETTE["ink"], (190, 102, 120, 7))
        bar_color = PALETTE["deep"] if self.rival_locked else PALETTE["coral"]
        pygame.draw.rect(surface, bar_color, (191, 103, round(118 * progress), 5))
        status = "LOCKED OUT" if self.rival_locked else "thinking" + "." * (1 + frame // 12 % 3)
        text(surface, f"{rival.name} {status}", (250, 113), 8, PALETTE["muted"] if self.rival_locked else PALETTE["cream"],
             center=True)
        # Question + answer box (bottom), like a battle.
        panel(surface, (7, 128, 306, 83), PALETTE["night"])
        if self.state == "countdown":
            count = 3 - (COUNTDOWN - self.timer) // 50
            label = "GO!" if count <= 0 else str(count)
            text(surface, label, (160, 166), 40, PALETTE["gold"], center=True, shadow=PALETTE["ink"])
            text(surface, f"{rival.name}: \"{rival.taunt}\"" if self.round == 1 else "Get ready...", (160, 200), 8,
                 PALETTE["muted"], center=True)
            return
        q = self.question
        header = (f"PUZZLE  •  {battle_puzzles.FORMAT_LABELS[q.format]}" if q.format != "standard"
                  else f"{topic_label(q.topic)}  •  {q.difficulty.upper()}")
        text(surface, header, (14, 133), 9, (190, 150, 255) if q.format != "standard" else PALETTE["gold"])
        wrapped(surface, q.prompt, (14, 145, 290, 24), 12, PALETTE["white"], 12, 2)
        if self.state == "reveal":
            verdict = {"you": ("YOU SCORE!", PALETTE["mint"]), "rival": (f"{rival.name} SCORES!", PALETTE["coral"]),
                       "none": ("TIME! No point.", PALETTE["muted"])}[self.winner]
            text(surface, verdict[0], (160, 176), 16, verdict[1], center=True, shadow=PALETTE["ink"])
            wrapped(surface, f"Answer: {q.answer}.  {q.steps[-1] if q.steps else q.explanation}",
                    (14, 189, 292, 20), 9, PALETTE["cream"], 10, 2)
            return
        jiggle = ((self.shake % 4) - 1.5) * 2 if self.shake else 0
        pygame.draw.rect(surface, PALETTE["coral"] if self.shake else PALETTE["gold"], (13 + jiggle, 171, 152, 21))
        pygame.draw.rect(surface, PALETTE["ink"], (14 + jiggle, 172, 150, 19))
        caret = "_" if frame % 50 < 28 else " "
        text(surface, "> " + self.answer.replace("*", "×").replace("x", "×") + caret, (19 + jiggle, 175), 14,
             PALETTE["cream"])
        seconds_left = max(0, (ROUND_LIMIT - self.round_frames) // 60)
        text(surface, f"{seconds_left}s", (305, 175), 11, PALETTE["muted"], align="right")
        if self.message:
            wrapped(surface, self.message, (14, 196, 292, 12), 9, PALETTE["gold"], 10, 1)
        if q.format == "target":
            numbers = q.visual[1]
            text(surface, "use " + ", ".join(map(str, numbers)) + " once each", (172, 176), 8, PALETTE["sky"])

    def _draw_result(self, surface, frame):
        r = self.result
        won = r["won"]
        title = "VICTORY!" if won else ("FORFEIT" if r["forfeit"] else "DEFEAT")
        text(surface, title, (160, 26), 30, PALETTE["gold"] if won else PALETTE["coral"], center=True, shadow=PALETTE["ink"])
        text(surface, f"{self.score[0]} - {self.score[1]} vs {self.rival.name}", (160, 52), 12, PALETTE["white"], center=True)
        line = self.rival.lose_line if won else self.rival.taunt
        wrapped(surface, f"{self.rival.name}: \"{line}\"", (30, 66, 260, 22), 9, PALETTE["muted"], 10, 2)
        panel(surface, (60, 92, 200, 58), PALETTE["night"], RANK_COLORS[r["rank"]])
        self._rank_badge(surface, 70, 100, r["rating"])
        color = PALETTE["mint"] if r["change"] >= 0 else PALETTE["coral"]
        text(surface, f"{r['old_rating']}  ->  {r['rating']}", (250, 102), 11, PALETTE["white"], align="right")
        text(surface, f"({r['change']:+d})", (250, 116), 11, color, align="right")
        if r["rank_up"] and frame % 40 < 30:
            text(surface, f"RANK UP!  {r['rank']}", (160, 136), 13, RANK_COLORS[r["rank"]], center=True)
        y = 160
        for reward in r["rewards"]:
            text(surface, reward, (160, y), 11, PALETTE["gold"], center=True)
            y += 13
        text(surface, "ENTER: BACK TO THE LADDER", (160, 228), 9, PALETTE["cream"], center=True)
