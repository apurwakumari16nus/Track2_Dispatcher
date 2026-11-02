import Foundation

/// Words reach the screen once two readings in a row agree on them, so what you see is not a guess that gets corrected a moment later.
struct SteadyWords {
    struct Part {
        var key: String
        var end: String.Index
    }

    private(set) var firm = ""
    private(set) var latest = ""

    mutating func read(_ reading: String) {
        let newer = Self.parts(reading), older = Self.parts(latest)
        latest = reading
        var agreed = 0
        while agreed < min(newer.count, older.count), newer[agreed].key == older[agreed].key { agreed += 1 }
        guard agreed > Self.parts(firm).count else { return }
        firm = String(reading[..<newer[agreed - 1].end])
    }

    /// What is left of some words once the first few are taken away.
    static func after(_ text: String, _ count: Int) -> String {
        let all = parts(text)
        guard count > 0 else { return text }
        guard count < all.count else { return "" }
        return String(text[all[count - 1].end...]).trimmingCharacters(in: .whitespaces.union(.punctuationCharacters))
    }

    /// One part per word, or per character in Chinese, which has no spaces. Punctuation and capitals do not count as a difference.
    static func parts(_ text: String) -> [Part] {
        var out: [Part] = []
        var run = ""
        var end = text.startIndex
        func close() {
            if !run.isEmpty { out.append(Part(key: run, end: end)) }
            run = ""
        }
        for index in text.indices {
            let character = text[index]
            if isHan(character) {
                close()
                out.append(Part(key: String(character), end: text.index(after: index)))
            } else if character.isLetter || character.isNumber {
                run += character.lowercased()
                end = text.index(after: index)
            } else {
                close()
            }
        }
        close()
        return out
    }

    private static func isHan(_ character: Character) -> Bool {
        guard let scalar = character.unicodeScalars.first?.value else { return false }
        return (0x4E00 ... 0x9FFF).contains(scalar) || (0x3400 ... 0x4DBF).contains(scalar)
    }
}
