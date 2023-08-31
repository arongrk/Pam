Pam von Aron Grabski

"Pam" ist dazu da die Daten des digitalen TDR von Gordon Notzon zu empfangen und zu verarbeiten.

In dem Ordner findet sich eine Datein namens "Digitales_TDR_Pam.exe" welche das Programm sofort startet. 

Wer das Programm weiter entwickeln möchte, kann den gesamten Ordner als Projekt in einer IDE öffnen, ich empfehle PyCharm. In dem Code befinden sich Kommentare und Erklärungen,
welche ich komplett auf englisch gehalten habe. 

In dem Ordner "resources" Befinden sich die Schriftarten, einige Logos und vor allem die UI files für das User-Interface.
Zum Erstellen dieser .ui Dateien habe ich den QT-Designer verwendet, der ist wirklich nur zu empfehlen. 

Die Pakete und Abhängigkteiten werden mit Poetry verwaltet. Das ermöglicht einen einfachen Start in eine Weiterentwicklung auf einem anderen Gerät. Um eine neue .exe Datei zu erstellen,
nachdem man weiter an dem Programm gearbeitet hat, kann der folgende Befehl in die Konsole eingegeben werden:

	poetry run pyinstaller --add-data "resources;resources" Digitales_TDR_Pam.py

Poetry muss dafür in der Pythoninstallation bereits installiert sein. 

Verwendet wird Python 3.10.11

Alle weiteren Versionseinschränkungen können in der pyproject.toml Datei im Hauptordner gefunden werden. 

Das komplette Programm basiert auf der PyQt5 Bibliothek, die Daten werden meist über Signale weitergeleitet. Um Verständnis von meinem Code zu erlangen, wird man sich zwangs-
läufig mit Pyqt5 genauer beschäftigen müssen. In der Hauptklasse von pam.py (UI) werden immer wieder Widgets verwendet, welche nicht vorher definiert werden. Diese werden mit
der .ui Datei in die Klasse geladen. 

Sollte es Schwierigkeiten mit dem Code oder der Bedienung der App geben, kann man mich gerne kontaktieren:

eMail: aron.grabski@gmail.com

Telefon: 0176 57615095

Der Github link für das Projekt lautet: https://github.com/arongrk/Pam

