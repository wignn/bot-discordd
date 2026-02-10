package htmlutil

import (
	"html"
	"regexp"
	"strings"
)

var (
	reScriptStyle = regexp.MustCompile(`(?is)<(script|style)[^>]*>.*?</\1>`)
	reHTMLTags    = regexp.MustCompile(`<[^>]+>`)
	reCDATA       = regexp.MustCompile(`<!\[CDATA\[(.*?)\]\]>`)
	reMultiNL     = regexp.MustCompile(`\n{3,}`)
	reMultiSpace  = regexp.MustCompile(`\s{2,}`)

	noisePatterns = []*regexp.Regexp{
		regexp.MustCompile(`(?i)Subscribe to.*?newsletter`),
		regexp.MustCompile(`(?i)Sign up for.*?alerts`),
		regexp.MustCompile(`(?im)Follow us on.*$`),
		regexp.MustCompile(`(?im)Read more:.*$`),
		regexp.MustCompile(`(?im)Related:.*$`),
	}

	reParagraphs = regexp.MustCompile(`(?is)<p[^>]*>(.*?)</p>`)
)

func StripTags(s string) string {
	s = reCDATA.ReplaceAllString(s, "$1")
	s = reScriptStyle.ReplaceAllString(s, "")
	s = reHTMLTags.ReplaceAllString(s, "")
	s = html.UnescapeString(s)
	return strings.TrimSpace(s)
}

func CleanContent(text string) string {
	text = reMultiNL.ReplaceAllString(text, "\n\n")
	text = reMultiSpace.ReplaceAllString(text, " ")
	for _, p := range noisePatterns {
		text = p.ReplaceAllString(text, "")
	}
	return strings.TrimSpace(text)
}

func ExtractSummary(description string, maxLen int) string {
	text := StripTags(description)
	text = CleanContent(text)

	if len(text) <= maxLen {
		return text
	}

	cutPos := strings.LastIndex(text[:maxLen], ".")
	if cutPos > maxLen/2 {
		return text[:cutPos+1]
	}

	cutPos = strings.LastIndex(text[:maxLen], " ")
	if cutPos > 0 {
		return text[:cutPos] + "..."
	}

	return text[:maxLen] + "..."
}

func ExtractParagraphs(htmlContent string) string {
	matches := reParagraphs.FindAllStringSubmatch(htmlContent, -1)
	if len(matches) == 0 {
		return StripTags(htmlContent)
	}

	var parts []string
	for _, m := range matches {
		cleaned := strings.TrimSpace(StripTags(m[1]))
		if cleaned != "" {
			parts = append(parts, cleaned)
		}
	}

	return strings.Join(parts, "\n\n")
}
