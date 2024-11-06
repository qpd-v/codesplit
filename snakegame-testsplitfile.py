import random
import sys
import pygame
import numpy as np
import pygame.sndarray

# Initialize pygame
pygame.init()

# Set up the game window
WIDTH = 800
HEIGHT = 600
GRID_SIZE = 20
GRID_WIDTH = WIDTH // GRID_SIZE
GRID_HEIGHT = HEIGHT // GRID_SIZE

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
PURPLE = (128, 0, 128)

# Game states
MENU = 0
PLAYING = 1
GAME_OVER = 2
PAUSED = 3

# Directions
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

class FrequencySweepGenerator:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        pygame.mixer.init(frequency=sample_rate, channels=1)

    def generate_sweep(self, start_freq, end_freq, duration):
        t = np.linspace(0, duration, int(self.sample_rate * duration))
        freq = np.exp(np.linspace(np.log(start_freq), np.log(end_freq), len(t)))
        sweep = np.sin(2 * np.pi * freq * t)
        return np.int16(sweep * 32767)

    def play_sweep(self, start_freq, end_freq, duration):
        sweep = self.generate_sweep(start_freq, end_freq, duration)
        sound = pygame.sndarray.make_sound(sweep)
        sound.play()

class SoundEffects:
    def __init__(self):
        self.sweep_generator = FrequencySweepGenerator()

    def play_eat_sound(self):
        self.sweep_generator.play_sweep(200, 600, 0.1)

    def play_death_sound(self):
        self.sweep_generator.play_sweep(400, 100, 0.3)

    def play_power_up_sound(self):
        self.sweep_generator.play_sweep(300, 900, 0.2)

class ParticleSystem:
    def __init__(self):
        self.particles = []

    def add_particle(self, x, y, color):
        num_particles = 10
        for _ in range(num_particles):
            angle = random.uniform(0, 2 * np.pi)
            speed = random.uniform(2, 5)
            self.particles.append({
                'x': x,
                'y': y,
                'vx': speed * np.cos(angle),
                'vy': speed * np.sin(angle),
                'color': color,
                'lifetime': 30
            })

    def update(self):
        for particle in self.particles[:]:
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']
            particle['lifetime'] -= 1
            if particle['lifetime'] <= 0:
                self.particles.remove(particle)

    def draw(self, screen):
        for particle in self.particles:
            alpha = int(255 * (particle['lifetime'] / 30))
            color = (*particle['color'][:3], alpha)
            surf = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (2, 2), 2)
            screen.blit(surf, (particle['x'], particle['y']))

class Snake:
    def __init__(self):
        self.body = [(GRID_WIDTH // 2, GRID_HEIGHT // 2)]
        self.direction = RIGHT
        self.grow = False
        self.velocity = 1

    def move(self):
        head = self.body[0]
        new_head = (head[0] + self.direction[0], head[1] + self.direction[1])
        self.body.insert(0, new_head)
        if not self.grow:
            self.body.pop()
        else:
            self.grow = False

    def change_direction(self, new_direction):
        # Ensure the snake cannot reverse
        if (new_direction[0] * -1, new_direction[1] * -1) != self.direction:
            self.direction = new_direction

    def check_collision(self):
        head = self.body[0]
        # Check for collisions with walls or self
        return (
            head[0] < 0 or head[0] >= GRID_WIDTH or
            head[1] < 0 or head[1] >= GRID_HEIGHT or
            head in self.body[1:]
        )

    def increase_speed(self):
        if self.velocity < 2:
            self.velocity += 1
        else:
            self.velocity = 1

class Food:
    def __init__(self, snake):
        self.snake = snake
        self.position = self.generate_position()

    def generate_position(self):
        while True:
            position = (random.randint(0, GRID_WIDTH - 1), random.randint(0, GRID_HEIGHT - 1))
            if position not in self.snake.body:
                return position

class PowerUp:
    def __init__(self, snake):
        self.snake = snake
        self.position = self.generate_position()
        self.type = random.choice(['speed', 'length', 'rainbow'])
        self.active = True

    def generate_position(self):
        while True:
            position = (random.randint(0, GRID_WIDTH - 1), random.randint(0, GRID_HEIGHT - 1))
            if position not in self.snake.body:
                return position

class Obstacle:
    def __init__(self, snake):
        self.snake = snake
        self.positions = self.generate_positions()

    def generate_positions(self):
        positions = []
        num_obstacles = random.randint(4, 9)
        for _ in range(num_obstacles):
            while True:
                pos = (random.randint(0, GRID_WIDTH - 1), random.randint(0, GRID_HEIGHT - 1))
                if pos not in self.snake.body:
                    positions.append(pos)
                    break
        return positions

    def draw(self, screen):
        for pos in self.positions:
            pygame.draw.rect(screen, BLUE, (pos[0] * GRID_SIZE, pos[1] * GRID_SIZE, GRID_SIZE, GRID_SIZE))

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Snake Game Extended")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.state = MENU
        self.snake = Snake()
        self.food = Food(self.snake)
        self.score = 0
        self.high_score = 0
        self.difficulty = 1
        self.speed = 10
        self.obstacle = Obstacle(self.snake)
        self.power_up = PowerUp(self.snake)
        self.sound_effects = SoundEffects()
        self.particle_system = ParticleSystem()
        self.rainbow_mode = False
        self.rainbow_offset = 0
        self.shake_frames = 0
        self.camera_offset = [0, 0]
        self.rainbow_duration = 0
        self.max_rainbow_duration = 300

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p and self.state == PLAYING:
                    self.state = PAUSED
                elif event.key == pygame.K_u and self.state == PAUSED:
                    self.state = PLAYING
                if self.state == PLAYING:
                    if event.key == pygame.K_UP:
                        self.snake.change_direction(UP)
                    elif event.key == pygame.K_DOWN:
                        self.snake.change_direction(DOWN)
                    elif event.key == pygame.K_LEFT:
                        self.snake.change_direction(LEFT)
                    elif event.key == pygame.K_RIGHT:
                        self.snake.change_direction(RIGHT)
                elif self.state == MENU:
                    if event.key == pygame.K_SPACE:
                        self.state = PLAYING
                elif self.state == GAME_OVER:
                    if event.key == pygame.K_SPACE:
                        self.reset_game()

    def update(self):
        if self.state == PLAYING:
            self.snake.move()
            self.particle_system.update()

            # Update rainbow mode duration
            if self.rainbow_mode:
                self.rainbow_duration -= 1
                if self.rainbow_duration <= 0:
                    self.rainbow_mode = False

            if self.snake.check_collision() or self.snake.body[0] in self.obstacle.positions:
                self.sound_effects.play_death_sound()
                self.state = GAME_OVER
            elif self.snake.body[0] == self.food.position:
                self.sound_effects.play_eat_sound()
                self.snake.grow = True
                self.food = Food(self.snake)
                self.score += 1
                self.particle_system.add_particle(
                    self.food.position[0] * GRID_SIZE,
                    self.food.position[1] * GRID_SIZE,
                    RED
                )
                self.shake_frames = 5
                if self.score > self.high_score:
                    self.high_score = self.score

            # Check for power-up collision
            if self.snake.body[0] == self.power_up.position and self.power_up.active:
                self.sound_effects.play_power_up_sound()
                self.handle_power_up(self.power_up.type)
                self.power_up.active = False
                self.power_up = PowerUp(self.snake)

            # Update screen shake
            if self.shake_frames > 0:
                self.camera_offset = [random.randint(-5, 5), random.randint(-5, 5)]
                self.shake_frames -= 1
            else:
                self.camera_offset = [0, 0]

            # Update rainbow effect
            if self.rainbow_mode:
                self.rainbow_offset += 1

    def draw(self):
        self.screen.fill(BLACK)
        if self.state == MENU:
            self.draw_menu()
        elif self.state == PLAYING:
            self.draw_game()
        elif self.state == GAME_OVER:
            self.draw_game_over()
        elif self.state == PAUSED:
            self.draw_pause()
        pygame.display.flip()

    def draw_menu(self):
        title = self.font.render("Snake Game - Extended", True, WHITE)
        start = self.font.render("Press SPACE to start", True, WHITE)
        difficulty = self.font.render(f"Difficulty: {self.difficulty}", True, WHITE)
        controls = self.font.render("Use arrow keys / 'P' to Pause", True, WHITE)
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 4))
        self.screen.blit(start, (WIDTH // 2 - start.get_width() // 2, HEIGHT // 2))
        self.screen.blit(difficulty, (WIDTH // 2 - difficulty.get_width() // 2, HEIGHT * 3 // 4))
        self.screen.blit(controls, (WIDTH // 2 - controls.get_width() // 2, HEIGHT * 3 // 4 + 40))

    def draw_game(self):
        game_surface = pygame.Surface((WIDTH, HEIGHT))
        game_surface.fill(BLACK)

        # Draw snake with rainbow effect if enabled
        for i, segment in enumerate(self.snake.body):
            if self.rainbow_mode:
                hue = (i * 10 + self.rainbow_offset) % 360
                color = pygame.Color(0)
                color.hsva = (hue, 100, 100, 100)
            else:
                color = GREEN
            pygame.draw.rect(
                game_surface,
                color,
                (segment[0] * GRID_SIZE, segment[1] * GRID_SIZE, GRID_SIZE, GRID_SIZE),
            )

        # Draw food
        pygame.draw.rect(
            game_surface,
            RED,
            (self.food.position[0] * GRID_SIZE, self.food.position[1] * GRID_SIZE, GRID_SIZE, GRID_SIZE),
        )

        # Draw power-up with conditional colors
        if self.power_up.active:
            color = BLUE if self.power_up.type == 'speed' else YELLOW if self.power_up.type == 'length' else PURPLE
            pygame.draw.rect(
                game_surface,
                color,
                (self.power_up.position[0] * GRID_SIZE, self.power_up.position[1] * GRID_SIZE, GRID_SIZE, GRID_SIZE),
            )

        # Draw obstacles
        self.obstacle.draw(game_surface)

        # Draw particles
        self.particle_system.draw(game_surface)

        score_text = self.font.render(f"Score: {self.score}", True, WHITE)
        game_surface.blit(score_text, (10, 10))

        if self.rainbow_mode:
            rainbow_timer = self.font.render(f"Rainbow: {self.rainbow_duration // 30}s", True, WHITE)
            game_surface.blit(rainbow_timer, (WIDTH - 255, 10))

        self.screen.blit(game_surface, self.camera_offset)

    def draw_pause(self):
        pause_text = self.font.render("PAUSED", True, WHITE)
        resume_text = self.font.render("Press 'U' to Resume", True, WHITE)
        self.screen.blit(pause_text, (WIDTH // 2 - pause_text.get_width() // 2, HEIGHT // 2))
        self.screen.blit(resume_text, (WIDTH // 2 - resume_text.get_width() // 2, HEIGHT // 2 + 40))

    def draw_game_over(self):
        game_over = self.font.render("Game Over", True, WHITE)
        score = self.font.render(f"Score: {self.score}", True, WHITE)
        high_score = self.font.render(f"High Score: {self.high_score}", True, WHITE)
        restart = self.font.render("Press SPACE to restart", True, WHITE)
        self.screen.blit(game_over, (WIDTH // 2 - game_over.get_width() // 2, HEIGHT // 4))
        self.screen.blit(score, (WIDTH // 2 - score.get_width() // 2, HEIGHT // 2))
        self.screen.blit(high_score, (WIDTH // 2 - high_score.get_width() // 2, HEIGHT // 2 + 40))
        self.screen.blit(restart, (WIDTH // 2 - restart.get_width() // 2, HEIGHT * 3 // 4))

    def handle_power_up(self, power_up_type):
        if power_up_type == 'speed':
            self.snake.increase_speed()
        elif power_up_type == 'length':
            self.snake.grow = True
            self.snake.grow = True  # Double growth for length power-up
        elif power_up_type == 'rainbow':
            self.rainbow_mode = True
            self.rainbow_duration = self.max_rainbow_duration

    def reset_game(self):
        self.state = PLAYING
        self.snake = Snake()
        self.food = Food(self.snake)
        self.score = 0
        self.obstacle = Obstacle(self.snake)
        self.power_up = PowerUp(self.snake)
        self.rainbow_mode = False
        self.shake_frames = 0
        self.camera_offset = [0, 0]
        self.rainbow_duration = 0

    def run(self):
        while True:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(30)  # Running the game at 30 FPS

if __name__ == "__main__":
    game = Game()
    game.run()