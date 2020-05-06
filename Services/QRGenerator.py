

class QRGenerator:
    def __init__(self):
        self._link = 'https://chart.googleapis.com/chart?chs=300x300&cht=qr&chl=#&choe=UTF-8'

    def generate_qr(self, wallet):
        return self._link.replace('#', wallet)
