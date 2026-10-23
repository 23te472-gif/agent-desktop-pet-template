"""Short, interruptible visual transitions; no timer or CLR dependency."""
class Tween:
    def __init__(self):
        self.start = 0.0
        self.origin = self.target = 0.0
        self.duration = .22

    def value(self, now):
        t = max(0.0, min(1.0, (now - self.start) / self.duration))
        eased = t * t * (3.0 - 2.0 * t)
        return self.origin + (self.target - self.origin) * eased

    def to(self, target, now, duration=.22):
        target = max(0.0, min(1.0, float(target)))
        if target == self.target:return
        self.origin = self.value(now)
        self.target = target
        self.start = now
        self.duration = max(.001, float(duration))

    def moving(self, now):
        return self.origin != self.target and now < self.start + self.duration
